"""Канал реального портала Bitrix24 (сценарий 1): токен, маппинг, идемпотентность,
исходящая отправка в открытую линию, секреты не в ответах/логах."""

from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.openlines as openlines_service
from app.agent.graph import build_graph
from app.agent.state import RetrievedChunk
from app.channels.bitrix.schemas import BitrixOpenLinesEvent
from app.core.config import Settings, settings
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.rag.retrieval import workspace_to_installation_id
from app.services import runtime_settings

PATH = "/webhook/bitrix/openlines"
DOMAIN = "portal.bitrix24.ru"
SECRET = "app-secret"
PORTAL = "https://portal.bitrix24.ru"


class _FakeBitrixClient:
    """Дубль Bitrix24RestClient: считает исходящие вызовы."""

    def __init__(self) -> None:
        self.send_message = AsyncMock(return_value={"result": True})
        self.download_image = AsyncMock(return_value="aW1hZ2U=")
        self.aclose = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture(autouse=True)
def _bitrix_env(monkeypatch: MonkeyPatch) -> None:
    """Конфигурация канала: секрет и портал для валидации и исходящих вызовов."""
    monkeypatch.setattr(settings, "bitrix_portal_url", PORTAL)
    monkeypatch.setattr(settings, "bitrix_app_user_id", "1")
    monkeypatch.setattr(settings, "bitrix_app_token", "out-token")
    monkeypatch.setattr(settings, "bitrix_application_token", SECRET)
    monkeypatch.setattr(settings, "bitrix_connector_id", "linetest")


@pytest.fixture
def fake_bitrix(monkeypatch: MonkeyPatch) -> _FakeBitrixClient:
    """Подменяет фабрику REST-клиента и OAuth-токен, чтобы не ходить в сеть."""
    client = _FakeBitrixClient()
    monkeypatch.setattr(openlines_service, "build_rest_client", lambda: client)
    monkeypatch.setattr(
        openlines_service,
        "get_current_access_token",
        AsyncMock(return_value="oauth-access-token"),
    )
    return client


@pytest.fixture
def cache_mocks(monkeypatch: MonkeyPatch) -> None:
    """Подменяет Redis-кэш графа, чтобы auto-тесты были герметичными."""
    import app.agent.graph as graph_mod

    monkeypatch.setattr(graph_mod, "get_kb_version", AsyncMock(return_value=3))
    monkeypatch.setattr(graph_mod, "get_cached_answer", AsyncMock(return_value=None))
    monkeypatch.setattr(graph_mod, "set_cached_answer", AsyncMock())


def _payload(
    *,
    chat_id: str = "chat-1",
    message_id: str = "msg-1",
    text: str = "как провести документ?",
    author_type: str | None = "client",
    author_id: str = "u1",
    domain: str = DOMAIN,
    secret: str = SECRET,
    with_chat_id: bool = True,
) -> dict[str, object]:
    """Событие открытой линии в формате REST-коннектора Bitrix24."""
    connector: dict[str, object] = {"connector_id": "linetest", "line_id": 1}
    if with_chat_id:
        connector["chat_id"] = chat_id
    message: dict[str, object] = {"id": message_id, "text": text}
    if author_type is not None:
        message["author"] = {"id": author_id, "type": author_type}
    else:
        message["user_id"] = author_id
    return {
        "data": {"connector": connector, "message": message},
        "auth": {"application_token": secret, "domain": domain},
    }


class _CountingGraph:
    """Считает запуски ainvoke, чтобы проверять повтор графа."""

    def __init__(self, inner: object, calls: list[int]) -> None:
        self._inner = inner
        self._calls = calls

    def ainvoke(self, *args: object, **kwargs: object) -> object:
        self._calls[0] += 1
        return self._inner.ainvoke(*args, **kwargs)  # type: ignore[attr-defined]


def _patch_auto_graph(
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    *,
    answer: str = "Ответ в канал",
    calls: list[int] | None = None,
    weak: bool = False,
) -> None:
    """Граф с высоким (0.9) или низким (0.3) скором подменяет get_graph."""
    import app.services.agent as agent_service

    score = 0.3 if weak else 0.9

    async def hit(_state: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(uuid4()),
                title="Инструкция",
                chunk_text="провести",
                score=score,
            )
        ]

    llm_mock.generate = AsyncMock(return_value=answer)  # type: ignore[attr-defined]
    graph = build_graph(llm_mock, app_settings, retriever=hit)  # type: ignore[arg-type]
    if calls is None:
        monkeypatch.setattr(agent_service, "get_graph", lambda: graph)
    else:
        monkeypatch.setattr(
            agent_service, "get_graph", lambda: _CountingGraph(graph, calls)
        )


# ── Приём и валидация ────────────────────────────────────────────────────


async def test_first_guest_message_creates_conversation_and_sends_reply(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["reply"] == "Ответ в канал"
    assert body["escalated"] is False
    assert body["delivered"] is True
    conversation_id = UUID(body["conversation_id"])

    mapping = (
        await db_session.scalars(
            select(ChannelThread).where(ChannelThread.thread_id == "chat-1")
        )
    ).first()
    assert mapping is not None
    assert mapping.channel == "bitrix_openlines"
    assert mapping.installation_id == workspace_to_installation_id(DOMAIN)
    assert mapping.conversation_id == conversation_id

    conversation = await db_session.get(Conversation, conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.OPEN
    users = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == MessageRole.USER,
                )
            )
        ).all()
    )
    assert len(users) == 1
    assert users[0].content == "как провести документ?"
    assert users[0].channel == "bitrix_openlines"
    assert users[0].channel_message_id == "msg-1"

    assert fake_bitrix.send_message.await_count == 1
    await_args = fake_bitrix.send_message.await_args
    assert await_args is not None
    assert await_args.kwargs["chat_id"] == "chat-1"
    assert await_args.kwargs["text"] == "Ответ в канал"
    assert await_args.kwargs["connector_id"] == "linetest"


async def test_invalid_token_rejected_403_without_state(
    api_client: AsyncClient,
    db_session: AsyncSession,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(PATH, json=_payload(secret="wrong-secret"))
    assert response.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0
    fake_bitrix.send_message.assert_not_awaited()


async def test_unconfigured_channel_fails_closed(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    monkeypatch.setattr(settings, "bitrix_application_token", "")
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0
    fake_bitrix.send_message.assert_not_awaited()


async def test_domain_mismatch_rejected_403(
    api_client: AsyncClient,
    db_session: AsyncSession,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(PATH, json=_payload(domain="evil.bitrix24.ru"))
    assert response.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0


async def test_missing_chat_id_rejected_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(
        PATH, json=_payload(with_chat_id=False, message_id="msg-x")
    )
    assert response.status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0


# ── Идемпотентность и маппинг ────────────────────────────────────────────


async def test_duplicate_event_not_rerun_and_not_resent(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    calls: list[int] = [0]
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, calls=calls)

    first = await api_client.post(PATH, json=_payload())
    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert calls[0] == 1

    second = await api_client.post(PATH, json=_payload())
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["conversation_id"] == first.json()["conversation_id"]
    assert calls[0] == 1
    assert fake_bitrix.send_message.await_count == 1

    count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == UUID(first.json()["conversation_id"]))
    )
    assert count == 2  # user + assistant, без дубля


async def test_escalation_sends_no_reply(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, weak=True)
    response = await api_client.post(
        PATH, json=_payload(text="не знаю", message_id="weak-1")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["escalated"] is True
    assert body["reply"] is None
    assert body["delivered"] is False
    fake_bitrix.send_message.assert_not_awaited()

    conversation = await db_session.get(Conversation, UUID(body["conversation_id"]))
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED


async def test_operator_event_persists_without_graph_or_send(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    import app.services.agent as agent_service

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен запускаться")),
    )
    response = await api_client.post(
        PATH, json=_payload(author_type="operator", message_id="op-1", text="Я помогу")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    fake_bitrix.send_message.assert_not_awaited()

    operators = list(
        (
            await db_session.scalars(
                select(Message).where(Message.role == MessageRole.OPERATOR)
            )
        ).all()
    )
    assert len(operators) == 1
    assert operators[0].content == "Я помогу"
    assert operators[0].channel == "bitrix_openlines"
    assert operators[0].channel_message_id == "op-1"


async def test_same_chat_id_other_portal_gets_own_conversation(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    """Масштабирование маппинга по установке (uuid5 от домена) проверяется
    на уровне сервиса: роутер валидирует домен до обработки события."""
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, answer="ответ")
    payload_a = BitrixOpenLinesEvent.model_validate(
        _payload(chat_id="chat-1", message_id="msg-a")
    )
    payload_b = BitrixOpenLinesEvent.model_validate(
        _payload(
            chat_id="chat-1",
            message_id="msg-b",
            domain="other.bitrix24.ru",
            secret="other-secret",
        )
    )
    first = await openlines_service.process_openlines_event(db_session, payload_a)
    second = await openlines_service.process_openlines_event(db_session, payload_b)
    assert first.status == "processed"
    assert second.status == "processed"
    assert first.conversation_id != second.conversation_id

    mappings = list(
        (
            await db_session.scalars(
                select(ChannelThread).where(ChannelThread.thread_id == "chat-1")
            )
        ).all()
    )
    assert len(mappings) == 2
    assert mappings[0].installation_id != mappings[1].installation_id


# ── Схемы и секреты ──────────────────────────────────────────────────────


def test_openlines_event_schema_parses_full_and_minimal() -> None:
    full = BitrixOpenLinesEvent.model_validate(
        _payload(
            chat_id="c9",
            message_id="m9",
            text="вопрос",
            author_type="client",
            domain=DOMAIN,
        )
    )
    assert full.data is not None
    assert full.data.connector is not None
    assert full.data.connector.chat_id == "c9"
    assert full.data.message is not None
    assert full.data.message.id == "m9"
    assert full.data.message.author is not None
    assert full.data.message.author.type == "client"
    assert full.auth is not None
    assert full.auth.application_token == SECRET

    minimal = BitrixOpenLinesEvent.model_validate({"auth": {"application_token": "x"}})
    assert minimal.auth is not None
    assert minimal.auth.application_token == "x"
    assert minimal.data is None

    # Либеральность: лишние ключи (ts, event и т.п.) не ломают парсинг.
    with_junk = {"ts": 123, "event": "ONIMCONNECTORMESSAGEADD", **_payload()}
    parsed = BitrixOpenLinesEvent.model_validate(with_junk)
    assert parsed.data is not None
    assert parsed.data.message is not None
    assert parsed.data.message.text == "как провести документ?"


async def test_secrets_do_not_leak_into_response_or_logs(
    api_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    body_str = response.text
    assert "app-secret" not in body_str
    assert "out-token" not in body_str

    for record in caplog.records:
        assert SECRET not in record.message
        assert "out-token" not in record.message


async def test_same_chat_id_same_portal_reuses_conversation(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    first = await api_client.post(PATH, json=_payload(message_id="m1"))
    second = await api_client.post(
        PATH, json=_payload(message_id="m2", text="второй вопрос")
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["conversation_id"] == second.json()["conversation_id"]

    mappings = list(
        (
            await db_session.scalars(
                select(ChannelThread).where(ChannelThread.thread_id == "chat-1")
            )
        ).all()
    )
    assert len(mappings) == 1
    users = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.channel == "bitrix_openlines",
                    Message.role == MessageRole.USER,
                )
            )
        ).all()
    )
    assert len(users) == 2  # две реплики, один диалог
