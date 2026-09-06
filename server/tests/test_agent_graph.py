"""Тесты стартовых узлов и графа LangGraph (classify правилами, скор ретривала)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.agent.nodes.classify import (
    _EMPTY_REPLY,
    _GREETING_REPLY,
    _OFF_TOPIC_REPLY,
    classify,
)
from app.agent.nodes.generate import generate
from app.agent.state import AgentState, RetrievedChunk
from app.core.config import Settings
from app.schemas.chat import ChatRequest
from app.services.agent import run_chat_turn

_INSTALLATION_ID = "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11"
_OTHER_INSTALLATION_ID = "0e3a0f4a-0000-4000-8000-000000000002"


def _state(**overrides: object) -> AgentState:
    base: AgentState = {
        "text": "Как провести документ?",
        "image_base64": None,
        "query": "",
        "intent": "empty",
        "chunks": [],
        "answer": "",
        "confidence": 0.0,
        "escalated": False,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _chunk(score: float, document_id: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=str(UUID(int=document_id)),
        title="Инструкция",
        chunk_text="провести документ в 1С",
        score=score,
    )


async def _hit_retriever(state: AgentState) -> list[RetrievedChunk]:
    """Ретривал выше порога уверенности — граф доходит до generate."""
    return [_chunk(0.9)]


async def _empty_retriever(state: AgentState) -> list[RetrievedChunk]:
    """Ничего не нашли — граф эскалирует, не вызывая generate."""
    return []


@pytest.fixture
def cache_mocks(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    """Подменяет Redis-кэш ответа в графе, возвращает (чтение, запись)."""
    import app.agent.graph as graph_mod

    lookup = AsyncMock(return_value=None)
    written = AsyncMock()
    monkeypatch.setattr(graph_mod, "get_kb_version", AsyncMock(return_value=3))
    monkeypatch.setattr(graph_mod, "get_cached_answer", lookup)
    monkeypatch.setattr(graph_mod, "set_cached_answer", written)
    return lookup, written


async def test_empty_input_skips_llm(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text=None, image_base64=None))
    assert result["intent"] == "empty"
    assert result["answer"] == _EMPTY_REPLY
    assert result["escalated"] is False
    llm_mock.generate.assert_not_called()
    llm_mock.chat_with_vision.assert_not_called()


async def test_greeting_skips_retrieve(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="привет"))
    assert result["intent"] == "greeting"
    assert result["answer"] == _GREETING_REPLY
    assert result["confidence"] == 1.0
    assert result["escalated"] is False
    assert result["chunks"] == []
    llm_mock.generate.assert_not_called()


async def test_off_topic_skips_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="какая у вас погода"))
    assert result["intent"] == "off_topic"
    assert result["answer"] == _OFF_TOPIC_REPLY
    llm_mock.generate.assert_not_called()


async def test_support_retrieves_then_generates(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    result = await graph.ainvoke(_state())
    assert result["intent"] == "support"
    assert result["answer"] == "Ответ из базы"
    assert result["confidence"] == 0.9
    assert result["escalated"] is False
    assert llm_mock.generate.await_count == 1


async def test_support_below_threshold_escalates_without_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(return_value="никогда не вызван")

    async def low_score_retriever(state: AgentState) -> list[RetrievedChunk]:
        return [_chunk(0.4, document_id=2)]

    graph = build_graph(llm_mock, app_settings, retriever=low_score_retriever)
    result = await graph.ainvoke(_state())
    assert result["escalated"] is True
    assert result["confidence"] == 0.4
    assert result["answer"] == ""
    llm_mock.generate.assert_not_called()


async def test_support_no_chunks_escalates_without_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    result = await graph.ainvoke(_state())
    assert result["escalated"] is True
    assert result["confidence"] == 0.0
    llm_mock.generate.assert_not_called()


async def test_vision_enriches_query_then_classifies(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.chat_with_vision = AsyncMock(return_value="Ошибка 1С:8330, поле Договор")
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="что это?", image_base64="AAA"))
    llm_mock.chat_with_vision.assert_awaited_once()
    assert "что это?" in result["query"]


async def test_classify_rules() -> None:
    assert (await classify({"query": "привет!"}))["intent"] == "greeting"
    assert (await classify({"query": "спасибо"}))["intent"] == "greeting"
    assert (await classify({"query": "как провести документ"}))["intent"] == "support"
    assert (await classify({"query": "привет, как провести документ"}))[
        "intent"
    ] == "support"
    assert (await classify({"query": "какая у вас погода"}))["intent"] == "off_topic"
    assert (await classify({"query": "ты натурал?"}))["intent"] == "off_topic"
    assert (await classify({"query": "не понимаю как поднять сервер ?"}))[
        "intent"
    ] == "support"
    assert (await classify({"query": "как настроить доступ"}))["intent"] == "support"
    empty = await classify({"query": "   "})
    assert empty["intent"] == "empty"
    assert empty["answer"] == _EMPTY_REPLY


@pytest.mark.parametrize(
    "query",
    [
        "ошибка при проведении накладной",
        "проблема с отчетом по НДС",
        "настройки не сохраняются",
        "обновление конфигурации упало",
        "зарплата не начисляется",
        "не проводится накладная",
        "блокировка при записи документа",
        "здравствуйте, не открывается 1с",
    ],
)
async def test_classify_matches_word_forms(query: str) -> None:
    """Элементы _SUPPORT_RE — основы: словоформы не должны уходить в off_topic."""
    assert (await classify({"query": query}))["intent"] == "support"


async def test_run_chat_turn_maps_contract_and_persists(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import select

    import app.services.agent as agent_service
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.escalation import Escalation
    from app.models.message import Message

    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.message_id == chat_request.message_id
    assert response.escalated is True
    assert response.confidence == 0.0
    assert response.sources == []
    assert isinstance(response.conversation_id, UUID)
    # гость получает непустой текст про передачу оператору
    assert response.text and "оператор" in response.text

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED

    messages = list(
        (
            await db_session.scalars(
                select(Message).where(Message.conversation_id == conversation.id)
            )
        ).all()
    )
    roles = {m.role for m in messages}
    assert MessageRole.USER in roles
    assert MessageRole.SYSTEM in roles

    escalation = (
        await db_session.scalars(
            select(Escalation).where(Escalation.conversation_id == conversation.id)
        )
    ).first()
    assert escalation is not None
    assert escalation.escalated_to
    assert conversation.suggested_response is None


async def test_run_chat_turn_replay_does_not_double_escalate(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import func, select

    import app.services.agent as agent_service
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus
    from app.models.escalation import Escalation

    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    first = await run_chat_turn(chat_request, db_session)
    # повтор того же хода против того же диалога
    replay_request = chat_request.model_copy(
        update={"conversation_id": first.conversation_id}
    )
    await run_chat_turn(replay_request, db_session)

    conversation = await db_session.get(Conversation, first.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    count = await db_session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.conversation_id == first.conversation_id)
    )
    assert count == 1


async def test_cache_hit_skips_generate(
    cache_mocks: tuple[AsyncMock, AsyncMock],
    llm_mock: MagicMock,
    app_settings: Settings,
) -> None:
    lookup, _ = cache_mocks
    chunk = _chunk(0.9)
    lookup.return_value = {"answer": "из кэша", "chunks": [chunk]}

    async def forbidden_retriever(state: AgentState) -> list[RetrievedChunk]:
        raise AssertionError("retrieve не должен вызываться")

    graph = build_graph(llm_mock, app_settings, retriever=forbidden_retriever)
    result = await graph.ainvoke(_state(installation_id=_INSTALLATION_ID))
    assert result["answer"] == "из кэша"
    # цитаты приходят вместе с ответом, иначе на попадании их бы не было
    assert result["chunks"] == [chunk]
    llm_mock.generate.assert_not_called()
    assert lookup.await_args is not None
    assert lookup.await_args.args[2] == _INSTALLATION_ID


async def test_cache_key_is_scoped_to_installation(
    cache_mocks: tuple[AsyncMock, AsyncMock],
    llm_mock: MagicMock,
    app_settings: Settings,
) -> None:
    _, written = cache_mocks
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")

    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    await graph.ainvoke(_state(installation_id=_OTHER_INSTALLATION_ID))

    assert written.await_args is not None
    assert written.await_args.kwargs["installation_id"] == _OTHER_INSTALLATION_ID


async def test_history_turn_bypasses_answer_cache(
    cache_mocks: tuple[AsyncMock, AsyncMock],
    llm_mock: MagicMock,
    app_settings: Settings,
) -> None:
    """Ответ по истории диалога нельзя ни отдать, ни записать в общий кэш."""
    lookup, written = cache_mocks
    lookup.return_value = {"answer": "из кэша", "chunks": []}
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")

    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    result = await graph.ainvoke(
        _state(
            installation_id=_INSTALLATION_ID,
            history=[{"role": "user", "content": "как провести документ"}],
        )
    )

    lookup.assert_not_awaited()
    written.assert_not_awaited()
    assert result["answer"] != "из кэша"


async def test_generate_includes_history(llm_mock: MagicMock) -> None:
    llm_mock.generate = AsyncMock(return_value="уточнение")
    await generate(
        {
            "query": "а как именно?",
            "chunks": [],
            "history": [
                {"role": "user", "content": "как провести документ"},
                {"role": "assistant", "content": "нажмите Провести"},
            ],
            "intent": "support",
        },
        llm=llm_mock,
    )
    prompt = llm_mock.generate.await_args.args[0][1]["content"]
    assert "как провести документ" in prompt
    assert "нажмите Провести" in prompt
    assert "а как именно?" in prompt


async def test_draft_hold_skips_graph(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import func, select

    import app.services.agent as agent_service
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message
    from app.services.conversation_status import transition_status

    conversation = Conversation(
        installation_id=UUID(_INSTALLATION_ID),
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="первый вопрос",
        )
    )
    conversation.suggested_response = "старый черновик"
    await db_session.commit()

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен вызываться")),
    )
    replay = chat_request.model_copy(
        update={
            "conversation_id": conversation.id,
            "workspace_id": _INSTALLATION_ID,
            "text": "уточнение",
        }
    )
    response = await run_chat_turn(replay, db_session)
    assert response.escalated is True
    llm_mock.generate.assert_not_called()
    user_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.USER,
        )
    )
    assert user_count == 2
    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 0
    await db_session.refresh(conversation)
    assert conversation.suggested_response == "старый черновик"


async def test_draft_hold_image_without_text_keeps_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import select

    import app.services.agent as agent_service
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message
    from app.services.conversation_status import transition_status

    conversation = Conversation(
        installation_id=UUID(_INSTALLATION_ID),
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    await db_session.commit()

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен вызываться")),
    )
    replay = chat_request.model_copy(
        update={
            "conversation_id": conversation.id,
            "workspace_id": _INSTALLATION_ID,
            "text": None,
            "image_base64": "aaa",
        }
    )
    await run_chat_turn(replay, db_session)
    rows = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.USER,
                )
            )
        ).all()
    )
    assert rows[-1].content == agent_service._IMAGE_HOLD_TEXT
    assert rows[-1].image_url is None
    llm_mock.generate.assert_not_called()


async def test_auto_escalated_high_score_keeps_status(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    cache_mocks: tuple[AsyncMock, AsyncMock],
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import func, select

    import app.services.agent as agent_service
    from app.core.config import settings
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message
    from app.services.conversation_status import transition_status

    monkeypatch.setattr(settings, "operator_assist_mode", "auto")
    llm_mock.generate = AsyncMock(return_value="Ответ в авто")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    conversation = Conversation(
        installation_id=UUID(_INSTALLATION_ID),
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    await db_session.commit()

    replay = chat_request.model_copy(
        update={
            "conversation_id": conversation.id,
            "workspace_id": _INSTALLATION_ID,
            "text": "как провести документ",
        }
    )
    response = await run_chat_turn(replay, db_session)
    assert response.escalated is False
    assert response.text == "Ответ в авто"
    await db_session.refresh(conversation)
    assert conversation.status == ConversationStatus.ESCALATED
    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 1
    llm_mock.generate.assert_awaited()
    await db_session.refresh(conversation)
    assert conversation.suggested_response is None


async def test_auto_escalated_weak_score_skips_generate(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    cache_mocks: tuple[AsyncMock, AsyncMock],
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import func, select

    import app.services.agent as agent_service
    from app.core.config import settings
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message
    from app.services.conversation_status import transition_status

    monkeypatch.setattr(settings, "operator_assist_mode", "auto")
    llm_mock.generate = AsyncMock(return_value="не должен")
    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    conversation = Conversation(
        installation_id=UUID(_INSTALLATION_ID),
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    await db_session.commit()

    replay = chat_request.model_copy(
        update={
            "conversation_id": conversation.id,
            "workspace_id": _INSTALLATION_ID,
            "text": "как провести документ",
        }
    )
    response = await run_chat_turn(replay, db_session)
    assert response.escalated is True
    assert "оператор" in response.text
    assert response.sources == []
    await db_session.refresh(conversation)
    assert conversation.status == ConversationStatus.ESCALATED
    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 0
    llm_mock.generate.assert_not_called()


async def test_resolved_chat_turn_rejected(
    chat_request: ChatRequest,
    db_session: AsyncSession,
) -> None:
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus
    from app.services.agent import ConversationConflictError
    from app.services.conversation_status import transition_status

    conversation = Conversation(
        installation_id=UUID(_INSTALLATION_ID),
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    transition_status(conversation, ConversationStatus.RESOLVED)
    await db_session.commit()

    replay = chat_request.model_copy(
        update={
            "conversation_id": conversation.id,
            "workspace_id": _INSTALLATION_ID,
        }
    )
    with pytest.raises(ConversationConflictError):
        await run_chat_turn(replay, db_session)
