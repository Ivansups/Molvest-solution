"""Бот открытой линии Bitrix24 (сценарий 1 ТЗ): рядом с кастомным коннектором."""

from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.channels.bitrix.oauth as oauth
import app.channels.bitrix.register_bot as register_bot
import app.services.ol_bot as ol_bot_service
import app.services.openlines as openlines_service
from app.agent.graph import build_graph
from app.agent.state import RetrievedChunk
from app.channels.bitrix.rest import Bitrix24RestClient
from app.channels.bitrix.schemas import (
    BitrixBotEvent,
    BitrixOpenLinesEvent,
    php_form_to_mapping,
)
from app.core.config import Settings, settings
from app.models.bitrix_oauth import BitrixOAuthToken
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.services import runtime_settings

PATH = "/webhook/bitrix/bot"
INSTALL_PATH = "/webhook/bitrix/install"
OPENLINES_PATH = "/webhook/bitrix/openlines"
DOMAIN = "portal.bitrix24.ru"
SECRET = "app-secret"
PORTAL = "https://portal.bitrix24.ru"
BOT_ID = "77"


class _FakeBitrixClient:
    """Дубль клиента: исходящие imbot.* / list / register."""

    def __init__(self) -> None:
        self.send_bot_message = AsyncMock(return_value={"result": True})
        self.send_message = AsyncMock(return_value={"result": True})
        self.download_image = AsyncMock(return_value="aW1hZ2U=")
        self.list_bots = AsyncMock(return_value={"result": {}})
        self.register_openlines_bot = AsyncMock(return_value={"result": 55})
        self.aclose = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture(autouse=True)
def _bitrix_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bitrix_portal_url", PORTAL)
    monkeypatch.setattr(settings, "bitrix_app_user_id", "1")
    monkeypatch.setattr(settings, "bitrix_app_token", "out-token")
    monkeypatch.setattr(settings, "bitrix_application_token", SECRET)
    monkeypatch.setattr(settings, "bitrix_connector_id", "linetest")
    monkeypatch.setattr(settings, "bitrix_bot_code", "molvest_support")
    monkeypatch.setattr(settings, "bitrix_handler_base_url", "")


@pytest.fixture
def fake_bitrix(monkeypatch: MonkeyPatch) -> _FakeBitrixClient:
    client = _FakeBitrixClient()
    monkeypatch.setattr(ol_bot_service, "build_rest_client", lambda: client)
    monkeypatch.setattr(
        ol_bot_service,
        "get_current_access_token",
        AsyncMock(return_value="oauth-access-token"),
    )
    monkeypatch.setattr(register_bot, "build_rest_client", lambda: client)
    return client


@pytest.fixture
def cache_mocks(monkeypatch: MonkeyPatch) -> None:
    import app.agent.graph as graph_mod

    monkeypatch.setattr(graph_mod, "get_kb_version", AsyncMock(return_value=3))
    monkeypatch.setattr(graph_mod, "get_cached_answer", AsyncMock(return_value=None))
    monkeypatch.setattr(graph_mod, "set_cached_answer", AsyncMock())


async def _seed_bot(db_session: AsyncSession, bot_id: str = BOT_ID) -> None:
    await oauth.store_installation(
        db_session,
        member_id="member-bot",
        access_token="oauth-access-token",
        refresh_token="refresh-bot",
        expires_in=3600,
    )
    row = (
        await db_session.scalars(
            select(BitrixOAuthToken).where(BitrixOAuthToken.member_id == "member-bot")
        )
    ).first()
    assert row is not None
    row.openlines_bot_id = bot_id
    await db_session.commit()


def _payload(
    *,
    dialog_id: str = "chat-bot-1",
    message_id: str = "b-msg-1",
    text: str = "как провести документ?",
    from_user: str = "u1",
    author_type: str | None = None,
    domain: str = DOMAIN,
    secret: str = SECRET,
    event: str = "ONIMBOTMESSAGEADD",
    with_dialog: bool = True,
) -> dict[str, object]:
    params: dict[str, object] = {
        "MESSAGE": text,
        "MESSAGE_ID": message_id,
        "FROM_USER_ID": from_user,
    }
    if with_dialog:
        params["DIALOG_ID"] = dialog_id
    if author_type is not None:
        params["AUTHOR_TYPE"] = author_type
    return {
        "event": event,
        "data": {"PARAMS": params, "BOT": {"BOT_ID": BOT_ID}},
        "auth": {"application_token": secret, "domain": domain},
    }


class _CountingGraph:
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
    answer: str = "Ответ в чат",
    calls: list[int] | None = None,
    weak: bool = False,
) -> None:
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


# ── Схемы ────────────────────────────────────────────────────────────────


def test_bot_event_schema_parses_full_and_minimal() -> None:
    full = BitrixBotEvent.model_validate(_payload())
    assert full.event == "ONIMBOTMESSAGEADD"
    assert full.data is not None
    assert full.data.PARAMS is not None
    assert full.data.PARAMS.DIALOG_ID == "chat-bot-1"
    assert full.data.PARAMS.MESSAGE_ID == "b-msg-1"
    assert full.auth is not None
    assert full.auth.application_token == SECRET

    lower = BitrixBotEvent.model_validate(
        {
            "event": "ONIMBOTMESSAGEADD",
            "data": {"params": {"dialog_id": "d2", "message": "hi", "message_id": 3}},
            "auth": {"application_token": "x", "domain": DOMAIN},
        }
    )
    assert lower.data is not None
    assert lower.data.PARAMS is not None
    assert lower.data.PARAMS.DIALOG_ID == "d2"
    assert lower.data.PARAMS.MESSAGE == "hi"

    minimal = BitrixBotEvent.model_validate({"event": "ONIMBOTJOINCHAT"})
    assert minimal.data is None


def test_php_form_to_mapping_nests_keys() -> None:
    nested = php_form_to_mapping(
        {
            "event": "ONIMBOTMESSAGEADD",
            "data[PARAMS][DIALOG_ID]": "chat9",
            "data[PARAMS][MESSAGE]": "вопрос",
            "auth[application_token]": SECRET,
            "auth[domain]": DOMAIN,
        }
    )
    data = nested["data"]
    assert isinstance(data, dict)
    params = data["PARAMS"]
    assert isinstance(params, dict)
    assert params["DIALOG_ID"] == "chat9"
    auth = nested["auth"]
    assert isinstance(auth, dict)
    assert auth["application_token"] == SECRET


# ── REST imbot.* ─────────────────────────────────────────────────────────


async def test_send_bot_message_uses_oauth_not_webhook_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"result": True})

    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await client.send_bot_message(
        bot_id="77",
        dialog_id="chat1",
        text="hi",
        access_token="oauth-secret",
    )
    assert "oauth-secret" in captured["url"]
    assert "webhook-secret" not in captured["url"]
    for record in caplog.records:
        if record.name.startswith("app."):
            assert "oauth-secret" not in record.message
            assert "webhook-secret" not in record.message
    await client.aclose()


async def test_register_openlines_bot_posts_handler_url() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"result": 55})

    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await client.register_openlines_bot(
        code="molvest_support",
        handler_url="https://example.ngrok-free.app/webhook/bitrix/bot",
        name="Молвест поддержка",
        access_token="oauth-secret",
    )
    assert "imbot.register" in str(captured["url"])
    assert "oauth-secret" in str(captured["url"])
    assert "/webhook/bitrix/bot" in str(captured["body"])
    await client.aclose()


# ── Install + регистрация бота ───────────────────────────────────────────


async def test_install_registers_bot_when_handler_set(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    monkeypatch.setattr(
        settings, "bitrix_handler_base_url", "https://ex.ngrok-free.app"
    )
    fake_bitrix.list_bots = AsyncMock(return_value={"result": {}})
    fake_bitrix.register_openlines_bot = AsyncMock(return_value={"result": 55})
    monkeypatch.setattr(register_bot, "build_rest_client", lambda: fake_bitrix)

    response = await api_client.post(
        INSTALL_PATH,
        data={
            "event": "ONAPPINSTALL",
            "auth[access_token]": "access-bot",
            "auth[refresh_token]": "refresh-bot",
            "auth[expires_in]": "3600",
            "auth[member_id]": "member-reg",
        },
    )
    assert response.status_code == 200
    fake_bitrix.register_openlines_bot.assert_awaited_once()
    row = (
        await db_session.scalars(
            select(BitrixOAuthToken).where(BitrixOAuthToken.member_id == "member-reg")
        )
    ).first()
    assert row is not None
    assert row.openlines_bot_id == "55"


async def test_install_reuses_existing_bot_by_code(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    monkeypatch.setattr(
        settings, "bitrix_handler_base_url", "https://ex.ngrok-free.app"
    )
    fake_bitrix.list_bots = AsyncMock(
        return_value={
            "result": {"55": {"CODE": "molvest_support", "ID": "55"}},
        }
    )
    fake_bitrix.register_openlines_bot = AsyncMock()
    monkeypatch.setattr(register_bot, "build_rest_client", lambda: fake_bitrix)

    response = await api_client.post(
        INSTALL_PATH,
        data={
            "auth[access_token]": "access-reuse",
            "auth[refresh_token]": "refresh-reuse",
            "auth[expires_in]": "3600",
            "auth[member_id]": "member-reuse",
        },
    )
    assert response.status_code == 200
    fake_bitrix.register_openlines_bot.assert_not_awaited()
    row = (
        await db_session.scalars(
            select(BitrixOAuthToken).where(BitrixOAuthToken.member_id == "member-reuse")
        )
    ).first()
    assert row is not None
    assert row.openlines_bot_id == "55"


async def test_install_without_handler_does_not_register(
    api_client: AsyncClient,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(
        INSTALL_PATH,
        data={
            "auth[access_token]": "access-skip",
            "auth[refresh_token]": "refresh-skip",
            "auth[expires_in]": "3600",
            "auth[member_id]": "member-skip",
        },
    )
    assert response.status_code == 200
    fake_bitrix.list_bots.assert_not_awaited()
    fake_bitrix.register_openlines_bot.assert_not_awaited()


# ── Webhook ──────────────────────────────────────────────────────────────


async def test_first_guest_message_creates_conversation_and_sends_bot_reply(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["reply"] == "Ответ в чат"
    assert body["delivered"] is True
    conversation_id = UUID(body["conversation_id"])

    mapping = (
        await db_session.scalars(
            select(ChannelThread).where(
                ChannelThread.channel == "bitrix_ol_bot",
                ChannelThread.thread_id == "chat-bot-1",
            )
        )
    ).first()
    assert mapping is not None
    assert mapping.conversation_id == conversation_id

    fake_bitrix.send_bot_message.assert_awaited_once()
    await_args = fake_bitrix.send_bot_message.await_args
    assert await_args is not None
    assert await_args.kwargs["dialog_id"] == "chat-bot-1"
    assert await_args.kwargs["text"] == "Ответ в чат"
    assert await_args.kwargs["bot_id"] == BOT_ID
    fake_bitrix.send_message.assert_not_awaited()


async def test_php_form_event_is_accepted(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(
        PATH,
        data={
            "event": "ONIMBOTMESSAGEADD",
            "data[PARAMS][DIALOG_ID]": "chat-form",
            "data[PARAMS][MESSAGE]": "как провести документ?",
            "data[PARAMS][MESSAGE_ID]": "form-1",
            "data[PARAMS][FROM_USER_ID]": "u1",
            "auth[application_token]": SECRET,
            "auth[domain]": DOMAIN,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"


async def test_invalid_token_rejected_403_without_state(
    api_client: AsyncClient,
    db_session: AsyncSession,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(PATH, json=_payload(secret="wrong-secret"))
    assert response.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0
    fake_bitrix.send_bot_message.assert_not_awaited()


async def test_missing_dialog_id_rejected_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    response = await api_client.post(PATH, json=_payload(with_dialog=False))
    assert response.status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0


async def test_welcome_event_ignored_without_graph(
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
        PATH,
        json={
            "event": "ONIMBOTJOINCHAT",
            "data": {"PARAMS": {"DIALOG_ID": "chat-join"}},
            "auth": {"application_token": SECRET, "domain": DOMAIN},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    fake_bitrix.send_bot_message.assert_not_awaited()
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0


async def test_duplicate_bot_event_not_rerun(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    calls: list[int] = [0]
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, calls=calls)
    first = await api_client.post(PATH, json=_payload())
    second = await api_client.post(PATH, json=_payload())
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    assert calls[0] == 1
    assert fake_bitrix.send_bot_message.await_count == 1


async def test_escalation_does_not_send_bot_message(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, weak=True)
    response = await api_client.post(
        PATH, json=_payload(text="не знаю", message_id="weak-b")
    )
    assert response.json()["escalated"] is True
    assert response.json()["delivered"] is False
    fake_bitrix.send_bot_message.assert_not_awaited()
    conversation = await db_session.get(
        Conversation, UUID(response.json()["conversation_id"])
    )
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED


async def test_operator_event_persists_without_graph(
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
        PATH,
        json=_payload(author_type="operator", message_id="op-b", text="Я помогу"),
    )
    assert response.status_code == 200
    fake_bitrix.send_bot_message.assert_not_awaited()
    operators = list(
        (
            await db_session.scalars(
                select(Message).where(Message.role == MessageRole.OPERATOR)
            )
        ).all()
    )
    assert len(operators) == 1
    assert operators[0].channel == "bitrix_ol_bot"


async def test_bot_echo_ignored(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    import app.services.agent as agent_service

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен запускаться")),
    )
    response = await api_client.post(
        PATH, json=_payload(from_user=BOT_ID, message_id="echo-1")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    fake_bitrix.send_bot_message.assert_not_awaited()
    assert await db_session.scalar(select(func.count()).select_from(Message)) == 0


async def test_bot_and_connector_same_id_are_separate_conversations(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    monkeypatch.setattr(openlines_service, "build_rest_client", lambda: fake_bitrix)
    monkeypatch.setattr(
        openlines_service,
        "get_current_access_token",
        AsyncMock(return_value="oauth-access-token"),
    )

    bot_event = BitrixBotEvent.model_validate(
        _payload(dialog_id="same-id", message_id="bot-side")
    )
    connector_event = BitrixOpenLinesEvent.model_validate(
        {
            "data": {
                "connector": {
                    "connector_id": "linetest",
                    "line_id": 1,
                    "chat_id": "same-id",
                },
                "message": {
                    "id": "conn-side",
                    "text": "как провести документ?",
                    "author": {"id": "u1", "type": "client"},
                },
            },
            "auth": {"application_token": SECRET, "domain": DOMAIN},
        }
    )
    bot_result = await ol_bot_service.process_bot_event(db_session, bot_event)
    conn_result = await openlines_service.process_openlines_event(
        db_session, connector_event
    )
    assert bot_result.conversation_id != conn_result.conversation_id
    mappings = list(
        (
            await db_session.scalars(
                select(ChannelThread).where(ChannelThread.thread_id == "same-id")
            )
        ).all()
    )
    channels = {item.channel for item in mappings}
    assert channels == {"bitrix_ol_bot", "bitrix_openlines"}


async def test_connector_webhook_still_works_after_bot(
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
    monkeypatch.setattr(openlines_service, "build_rest_client", lambda: fake_bitrix)
    monkeypatch.setattr(
        openlines_service,
        "get_current_access_token",
        AsyncMock(return_value="oauth-access-token"),
    )
    response = await api_client.post(
        OPENLINES_PATH,
        json={
            "data": {
                "connector": {
                    "connector_id": "linetest",
                    "line_id": 1,
                    "chat_id": "chat-1",
                },
                "message": {
                    "id": "msg-1",
                    "text": "как провести документ?",
                    "author": {"id": "u1", "type": "client"},
                },
            },
            "auth": {"application_token": SECRET, "domain": DOMAIN},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    mapping = (
        await db_session.scalars(
            select(ChannelThread).where(ChannelThread.channel == "bitrix_openlines")
        )
    ).first()
    assert mapping is not None
    fake_bitrix.send_message.assert_awaited()


async def test_secrets_not_in_bot_response_or_logs(
    api_client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_bitrix: _FakeBitrixClient,
) -> None:
    await _seed_bot(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    assert SECRET not in response.text
    assert "out-token" not in response.text
    assert "oauth-access-token" not in response.text
    for record in caplog.records:
        assert SECRET not in record.message
        assert "out-token" not in record.message
        assert "oauth-access-token" not in record.message
