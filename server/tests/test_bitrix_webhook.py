"""Вебхук живого Bitrix-треда: маппинг, идемпотентность, draft/auto."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.agent.state import RetrievedChunk
from app.core.config import Settings, settings
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.services import runtime_settings
from app.services.conversation_status import transition_status

INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_WORKSPACE = "another-workspace"

PATH = "/webhook/bitrix"


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture
def cache_mocks(monkeypatch: MonkeyPatch) -> None:
    """Подменяет Redis-кэш графа, чтобы auto-тесты были герметичными."""
    import app.agent.graph as graph_mod

    monkeypatch.setattr(graph_mod, "get_kb_version", AsyncMock(return_value=3))
    monkeypatch.setattr(graph_mod, "get_cached_answer", AsyncMock(return_value=None))
    monkeypatch.setattr(graph_mod, "set_cached_answer", AsyncMock())


def _payload(
    *,
    thread_id: str,
    message_id: str,
    sender: str = "user",
    text: str = "как провести документ?",
    workspace_id: str = str(INSTALL),
    user_id: str = "u1",
) -> dict[str, str | None]:
    return {
        "workspace_id": workspace_id,
        "thread_id": thread_id,
        "message_id": message_id,
        "sender": sender,
        "text": text,
        "user_id": user_id,
    }


def _mock_draft(
    monkeypatch: MonkeyPatch,
    answer: str = "Черновик агента",
    *,
    score: float = 0.9,
) -> None:
    """Подменяет retrieve+generate в services/draft.py."""
    import app.services.draft as draft_service

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
    )

    monkeypatch.setattr(
        draft_service,
        "make_retriever",
        lambda llm, cfg: AsyncMock(
            return_value=[
                RetrievedChunk(
                    document_id=str(uuid4()),
                    title="Инструкция",
                    chunk_text="провести",
                    score=score,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        draft_service,
        "generate",
        AsyncMock(return_value={"answer": answer, "confidence": score}),
    )


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
    llm_mock: MagicMock,
    app_settings: Settings,
    *,
    answer: str = "Ответ в авто",
    calls: list[int] | None = None,
) -> None:
    """Собирает граф с высоким/низким скором и подменяет get_graph в agent."""
    import app.services.agent as agent_service

    async def hit(_state: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(uuid4()),
                title="Инструкция",
                chunk_text="провести",
                score=0.9,
            )
        ]

    llm_mock.generate = AsyncMock(return_value=answer)
    graph = build_graph(llm_mock, app_settings, retriever=hit)
    if calls is None:
        monkeypatch.setattr(agent_service, "get_graph", lambda: graph)
    else:
        monkeypatch.setattr(
            agent_service, "get_graph", lambda: _CountingGraph(graph, calls)
        )


def _patch_auto_weak_graph(
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
) -> None:
    """Граф, который эскалирует: скор 0.3 ниже порога."""
    import app.services.agent as agent_service

    async def weak(_state: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(uuid4()),
                title="Инструкция",
                chunk_text="нет",
                score=0.3,
            )
        ]

    graph = build_graph(llm_mock, app_settings, retriever=weak)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)


async def test_first_user_message_creates_conversation_and_mapping(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    _mock_draft(monkeypatch)
    response = await api_client.post(
        PATH, json=_payload(thread_id="t1", message_id="m1")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["escalated"] is False
    assert body["draft"] == "Черновик агента"
    conversation_id = UUID(body["conversation_id"])

    mapping = (
        await db_session.scalars(
            select(ChannelThread).where(ChannelThread.thread_id == "t1")
        )
    ).first()
    assert mapping is not None
    assert mapping.channel == "bitrix"
    assert mapping.installation_id == INSTALL
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
    assert users[0].channel == "bitrix"
    assert users[0].channel_message_id == "m1"


async def test_duplicate_event_does_not_rerun_graph(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    calls: list[int] = [0]
    _patch_auto_graph(
        monkeypatch,
        llm_mock,
        app_settings,
        calls=calls,
    )

    first = await api_client.post(PATH, json=_payload(thread_id="t1", message_id="m1"))
    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert first.json()["reply"] == "Ответ в авто"
    assert calls[0] == 1

    second = await api_client.post(PATH, json=_payload(thread_id="t1", message_id="m1"))
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["conversation_id"] == first.json()["conversation_id"]
    assert calls[0] == 1

    count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == UUID(first.json()["conversation_id"]))
    )
    assert count == 2  # user + assistant, без дубля


async def test_draft_stores_suggestion_without_escalation(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    _mock_draft(monkeypatch, answer="Черновик", score=0.3)
    response = await api_client.post(
        PATH, json=_payload(thread_id="t2", message_id="m2", text="что делать?")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["draft"] == "Черновик"
    assert body["reply"] is None
    assert body["escalated"] is False
    conversation_id = UUID(body["conversation_id"])

    conversation = await db_session.get(Conversation, conversation_id)
    assert conversation is not None
    assert conversation.suggested_response == "Черновик"
    assert conversation.status == ConversationStatus.OPEN  # низкий скор не эскалирует

    messages = list(
        (
            await db_session.scalars(
                select(Message).where(Message.conversation_id == conversation_id)
            )
        ).all()
    )
    assert [m.role for m in messages] == [MessageRole.USER]
    escalations = await db_session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.conversation_id == conversation_id)
    )
    assert escalations == 0


async def test_auto_answers_user_on_high_confidence(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(
        PATH, json=_payload(thread_id="t3", message_id="m3")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["reply"] == "Ответ в авто"
    assert body["escalated"] is False
    conversation_id = UUID(body["conversation_id"])

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
    assistants = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == MessageRole.ASSISTANT,
                )
            )
        ).all()
    )
    assert len(users) == 1
    assert users[0].channel == "bitrix"
    assert users[0].channel_message_id == "m3"
    assert len(assistants) == 1
    assert assistants[0].content == "Ответ в авто"


async def test_auto_escalates_on_low_confidence(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_weak_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(
        PATH, json=_payload(thread_id="t4", message_id="m4", text="не знаю")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["escalated"] is True
    assert body["reply"] is None
    conversation_id = UUID(body["conversation_id"])

    conversation = await db_session.get(Conversation, conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response is None
    escalation = (
        await db_session.scalars(
            select(Escalation).where(Escalation.conversation_id == conversation_id)
        )
    ).first()
    assert escalation is not None
    systems = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == MessageRole.SYSTEM,
                )
            )
        ).all()
    )
    assert len(systems) == 1
    assert "оператор" in systems[0].content


async def test_operator_message_lefts_draft_and_skips_graph(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    _mock_draft(monkeypatch, answer="черновик остаётся")
    first = await api_client.post(
        PATH, json=_payload(thread_id="t5", message_id="m5", sender="user")
    )
    conversation_id = UUID(first.json()["conversation_id"])

    import app.services.agent as agent_service

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен вызываться")),
    )

    operator = await api_client.post(
        PATH,
        json=_payload(
            thread_id="t5",
            message_id="o1",
            sender="operator",
            text="Я помогу",
        ),
    )
    assert operator.status_code == 200
    assert operator.json()["status"] == "processed"

    conversation = await db_session.get(Conversation, conversation_id)
    assert conversation is not None
    assert conversation.suggested_response == "черновик остаётся"
    operators = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation_id,
                    Message.role == MessageRole.OPERATOR,
                )
            )
        ).all()
    )
    assert len(operators) == 1
    assert operators[0].content == "Я помогу"
    assert operators[0].channel == "bitrix"
    assert operators[0].channel_message_id == "o1"


async def test_duplicate_operator_event_single_message(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    _mock_draft(monkeypatch, answer="черновик")
    await api_client.post(
        PATH, json=_payload(thread_id="t5", message_id="m5", sender="user")
    )
    payload = _payload(
        thread_id="t5", message_id="o1", sender="operator", text="Я помогу"
    )
    first = await api_client.post(PATH, json=payload)
    second = await api_client.post(PATH, json=payload)
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"

    count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.channel == "bitrix",
            Message.channel_message_id == "o1",
            Message.role == MessageRole.OPERATOR,
        )
    )
    assert count == 1


async def test_mode_switch_draft_to_auto_without_restart(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    _mock_draft(monkeypatch, answer="черновик первой")
    first = await api_client.post(
        PATH, json=_payload(thread_id="t6", message_id="m6", text="первый вопрос")
    )
    assert first.json()["draft"] == "черновик первой"

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, answer="ответ в авто")
    second = await api_client.post(
        PATH,
        json=_payload(thread_id="t6", message_id="m7", text="второй вопрос"),
    )
    body = second.json()
    assert body["status"] == "processed"
    assert body["reply"] == "ответ в авто"
    assert body["conversation_id"] == first.json()["conversation_id"]


async def test_same_thread_other_installation_own_conversation(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    _mock_draft(monkeypatch, answer="черновик")
    first = await api_client.post(
        PATH,
        json=_payload(
            thread_id="t9",
            message_id="ma",
            workspace_id=str(INSTALL),
        ),
    )
    second = await api_client.post(
        PATH,
        json=_payload(
            thread_id="t9",
            message_id="mb",
            workspace_id=OTHER_WORKSPACE,
        ),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["conversation_id"] != second.json()["conversation_id"]

    mappings = list(
        (
            await db_session.scalars(
                select(ChannelThread).where(ChannelThread.thread_id == "t9")
            )
        ).all()
    )
    assert len(mappings) == 2
    assert mappings[0].installation_id != mappings[1].installation_id


async def test_invalid_sender_rejected_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await api_client.post(
        PATH, json=_payload(thread_id="t9", message_id="mx", sender="boss")
    )
    assert response.status_code == 422
    count = await db_session.scalar(select(func.count()).select_from(Message))
    assert count == 0


async def test_webhook_requires_internal_token(
    api_client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "secret")
    missing = await api_client.post(
        PATH, json=_payload(thread_id="t1", message_id="m1")
    )
    assert missing.status_code == 401
    wrong = await api_client.post(
        PATH,
        json=_payload(thread_id="t1", message_id="m1"),
        headers={"X-Internal-Token": "nope"},
    )
    assert wrong.status_code == 401


async def test_resolved_thread_returns_409(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = Conversation(
        installation_id=INSTALL,
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    transition_status(conversation, ConversationStatus.RESOLVED)
    db_session.add(
        ChannelThread(
            channel="bitrix",
            thread_id="t-resolved",
            installation_id=INSTALL,
            conversation_id=conversation.id,
        )
    )
    await db_session.commit()

    _mock_draft(monkeypatch, answer="не должен")
    user = await api_client.post(
        PATH,
        json=_payload(
            thread_id="t-resolved", message_id="m-r", sender="user", text="поздно"
        ),
    )
    assert user.status_code == 409
    operator = await api_client.post(
        PATH,
        json=_payload(
            thread_id="t-resolved", message_id="m-r2", sender="operator", text="нет"
        ),
    )
    assert operator.status_code == 409


async def test_agent_mode_high_score_holds_draft_without_guest_reply(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, answer="Ответ в авто")
    response = await api_client.post(
        PATH, json=_payload(thread_id="t-agent", message_id="m-agent")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalated"] is True
    assert body["reply"] is None
    conversation = await db_session.get(Conversation, UUID(body["conversation_id"]))
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Ответ в авто"
    assistants = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.ASSISTANT,
                )
            )
        ).all()
    )
    assert assistants == []


async def test_agent_mode_duplicate_event_is_idempotent(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: MagicMock,
    app_settings: Settings,
    cache_mocks: None,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    calls: list[int] = [0]
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, calls=calls)
    first = await api_client.post(
        PATH, json=_payload(thread_id="t-dup", message_id="m-dup")
    )
    second = await api_client.post(
        PATH, json=_payload(thread_id="t-dup", message_id="m-dup")
    )
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    assert calls[0] == 1
