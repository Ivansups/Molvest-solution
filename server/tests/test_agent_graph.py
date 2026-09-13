"""Тесты узлов и графа LangGraph (classify правилами, скор ретривала, handoff LLM)."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.agent.nodes.classify import _EMPTY_REPLY
from app.agent.nodes.generate import generate
from app.agent.nodes.router import (
    DETECTOR_FAILURE_REASON,
    HANDOFF_ESCALATION_REASON,
    route_intent,
)
from app.agent.prompts import (
    DEFAULT_AWAY_REPLY,
    DEFAULT_GREETING_REPLY,
)
from app.agent.state import AgentState, RetrievedChunk
from app.core.config import Settings
from app.core.gigachat_client import GigaChatError, GigaChatService
from app.core.openrouter_client import OpenRouterClassifier, OpenRouterError
from app.schemas.chat import ChatRequest
from app.services import runtime_settings
from app.services.agent import (
    AGENT_HOLD_REASON,
    apply_operator_reply_policy,
    run_chat_turn,
)
from app.services.conversations import GUEST_ESCALATION_TEXT

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


_ROUTER_DECISION = {
    "SUPPORT": "support",
    "HANDOFF": "handoff",
    "GREETING": "greeting",
    "AWAY_CHECK": "away",
    "OFFTOPIC": "offtopic",
}


def _classifier(
    decision: str = "SUPPORT", *, raises: bool = False, reply: str = ""
) -> MagicMock:
    """Мок intake-роутера OpenRouter: маршрут или сбой классификатора."""
    classifier = MagicMock(spec=OpenRouterClassifier)
    if raises:
        classifier.route = AsyncMock(side_effect=OpenRouterError("сбой классификатора"))
    else:
        classifier.route = AsyncMock(
            return_value={"intent": _ROUTER_DECISION[decision], "reply": reply}
        )
    classifier.is_configured.return_value = True
    return classifier


def _llm(*, handoff: bool = False, raises: bool = False) -> MagicMock:
    """Мок GigaChat: YES/NO хэндоффа или сбой Lite-классификации."""
    llm = MagicMock(spec=GigaChatService)
    llm.generate = AsyncMock(return_value="")
    llm.chat_with_vision = AsyncMock(return_value="")
    llm.get_embeddings = AsyncMock(return_value=[])
    if raises:
        llm.classify_handoff = AsyncMock(side_effect=GigaChatError("сбой GigaChat"))
    else:
        llm.classify_handoff = AsyncMock(return_value=handoff)
    return llm


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


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


async def test_greeting_and_off_topic_end_at_router(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """Приветствие/оффтоп отвечает роутер — retrieve и generate не вызываются."""

    async def forbidden_retriever(state: AgentState) -> list[RetrievedChunk]:
        raise AssertionError("retrieve не должен вызываться после ответа роутера")

    for text, decision, reply in (
        ("привет", "GREETING", "привет!"),
        ("какая у вас погода", "OFFTOPIC", "помогаю только по 1С"),
    ):
        graph = build_graph(
            llm_mock,
            app_settings,
            retriever=forbidden_retriever,
            handoff_classifier=_classifier(decision, reply=reply),
        )
        result = await graph.ainvoke(_state(text=text))
        assert result["intent"] == decision.lower()
        assert result["answer"] == reply
        assert result["escalated"] is False
        llm_mock.generate.assert_not_awaited()


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


async def test_vision_low_score_still_generates(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """Скриншот без попадания в БЗ — всё равно отвечаем по описанию Vision."""
    llm_mock.chat_with_vision = AsyncMock(return_value="Интерфейс Telegram")
    llm_mock.generate = AsyncMock(return_value="На скрине Telegram, не ошибка 1С.")
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_empty_retriever,
        handoff_classifier=_classifier(),
    )
    result = await graph.ainvoke(_state(text="что видишь?", image_base64="AAA"))
    assert result["escalated"] is False
    assert result["answer"] == "На скрине Telegram, не ошибка 1С."
    assert "Интерфейс Telegram" in result["query"]
    llm_mock.generate.assert_awaited_once()
    llm_mock.classify_handoff.assert_not_awaited()


async def test_route_intent_uses_guest_text_not_vision_dump() -> None:
    classifier = _classifier()
    llm = _llm()
    dump = "что видишь?\n\nОписание скриншота:\nCHAMPIONSHIP чат с Женей"
    result = await route_intent(
        {"text": "что видишь?", "query": dump},
        classifier=classifier,
        llm=llm,
    )
    assert result == {}
    classifier.route.assert_awaited_once_with("что видишь?")


async def test_route_intent_handoff_escalates() -> None:
    classifier = _classifier("HANDOFF")
    llm = _llm()
    result = await route_intent(
        {"query": "Позовите оператора"}, classifier=classifier, llm=llm
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    classifier.route.assert_awaited_once_with("Позовите оператора")
    llm.classify_handoff.assert_not_awaited()


async def test_route_intent_support_keeps_support() -> None:
    """«Как …» про оператора — запрос к базе знаний, не хэндофф и не оффтоп."""
    classifier = _classifier()
    llm = _llm()
    result = await route_intent(
        {"query": "как позвать оператора в 1с"}, classifier=classifier, llm=llm
    )
    assert result == {}
    classifier.route.assert_awaited_once_with("как позвать оператора в 1с")
    llm.classify_handoff.assert_not_awaited()


async def test_route_intent_offtopic_answers_without_llm() -> None:
    classifier = _classifier("OFFTOPIC", reply="помогаю только по 1С")
    llm = _llm()
    result = await route_intent(
        {"query": "какая у вас погода"}, classifier=classifier, llm=llm
    )
    assert result["intent"] == "offtopic"
    assert result["answer"] == "помогаю только по 1С"
    assert result["confidence"] == 1.0
    assert result["escalated"] is False
    llm.classify_handoff.assert_not_awaited()
    llm.generate.assert_not_awaited()


async def test_route_intent_greeting_falls_back_to_default_reply() -> None:
    classifier = _classifier("GREETING", reply="")
    llm = _llm()
    result = await route_intent({"query": "привет"}, classifier=classifier, llm=llm)
    assert result["intent"] == "greeting"
    assert result["answer"] == DEFAULT_GREETING_REPLY
    llm.generate.assert_not_awaited()


async def test_route_intent_openrouter_error_falls_back_to_rules_greeting() -> None:
    """Сбой OpenRouter — «привет» ловится правилами, GigaChat не трогаем."""
    classifier = _classifier(raises=True)
    llm = _llm(raises=True)
    result = await route_intent({"query": "привет"}, classifier=classifier, llm=llm)
    assert result["intent"] == "greeting"
    classifier.route.assert_awaited_once()
    llm.classify_handoff.assert_not_awaited()


async def test_route_intent_openrouter_error_rules_handoff() -> None:
    """Сбой OpenRouter — «позови оператора» решают правила без LLM."""
    classifier = _classifier(raises=True)
    llm = _llm(raises=True)
    result = await route_intent(
        {"query": "позови оператора"}, classifier=classifier, llm=llm
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    llm.classify_handoff.assert_not_awaited()


async def test_route_intent_openrouter_error_falls_back_to_gigachat_handoff() -> None:
    """Правила не решили — тот же YES/NO хэндоффа через GigaChat Lite."""
    classifier = _classifier(raises=True)
    llm = _llm(handoff=True)
    result = await route_intent(
        {"query": "Соедините с живым специалистом"},
        classifier=classifier,
        llm=llm,
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    classifier.route.assert_awaited_once()
    llm.classify_handoff.assert_awaited_once()


async def test_route_intent_both_fail_escalates() -> None:
    """Оба классификатора упали — тикет, не ответ из базы."""
    classifier = _classifier(raises=True)
    llm = _llm(raises=True)
    result = await route_intent(
        {"query": "Соедините с живым специалистом"},
        classifier=classifier,
        llm=llm,
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == DETECTOR_FAILURE_REASON
    llm.classify_handoff.assert_awaited_once()


async def test_route_intent_not_configured_uses_rules_away() -> None:
    """Пустой ключ OpenRouter — «ты тут?» отвечаем по правилам без LLM."""
    classifier = _classifier("HANDOFF")
    classifier.is_configured.return_value = False
    llm = _llm(raises=True)
    result = await route_intent({"query": "ты тут?"}, classifier=classifier, llm=llm)
    assert result["intent"] == "away"
    assert result["answer"] == DEFAULT_AWAY_REPLY
    classifier.route.assert_not_awaited()
    llm.classify_handoff.assert_not_awaited()


async def test_route_intent_not_configured_handoff_uses_gigachat() -> None:
    """Пустой ключ OpenRouter — хэндофф не выключается, решается GigaChat."""
    classifier = _classifier("HANDOFF")
    classifier.is_configured.return_value = False
    llm = _llm(handoff=True)
    result = await route_intent(
        {"query": "Соедините с живым специалистом"},
        classifier=classifier,
        llm=llm,
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    classifier.route.assert_not_awaited()
    llm.classify_handoff.assert_awaited_once()


async def test_route_intent_empty_query_skips() -> None:
    classifier = _classifier("HANDOFF")
    llm = _llm()
    result = await route_intent({"query": "   "}, classifier=classifier, llm=llm)
    assert result == {}
    classifier.route.assert_not_awaited()
    llm.classify_handoff.assert_not_awaited()


async def test_handoff_request_escalates_without_llm(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    async def forbidden_retriever(state: AgentState) -> list[RetrievedChunk]:
        raise AssertionError("retrieve не должен вызываться при хэндоффе")

    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=forbidden_retriever,
        handoff_classifier=_classifier("HANDOFF"),
    )
    result = await graph.ainvoke(_state(text="Позовите оператора"))
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    llm_mock.generate.assert_not_called()
    llm_mock.chat_with_vision.assert_not_called()


async def test_router_support_goes_through_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """Роутер не срезал «как позвать оператора в 1с» — граф идёт через RAG."""
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=_classifier(),
    )
    result = await graph.ainvoke(_state(text="как позвать оператора в 1с"))
    assert result["intent"] == "support"
    assert result["escalated"] is False
    assert result["answer"] == "Ответ из базы"
    llm_mock.generate.assert_awaited_once()


async def test_handoff_error_falls_back_to_gigachat(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """Сбой OpenRouter — GigaChat Lite классифицирует, retrieve не нужен при YES."""
    llm_mock.classify_handoff = AsyncMock(return_value=True)
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=_classifier(raises=True),
    )
    result = await graph.ainvoke(_state(text="Соедините с живым специалистом"))
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    llm_mock.classify_handoff.assert_awaited_once()
    llm_mock.generate.assert_not_called()


async def test_handoff_both_classifiers_fail_escalates(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """OpenRouter и GigaChat упали — эскалация, не автоответ из базы."""

    async def forbidden_retriever(state: AgentState) -> list[RetrievedChunk]:
        raise AssertionError("retrieve не должен вызываться при сбое детекта")

    llm_mock.classify_handoff = AsyncMock(side_effect=GigaChatError("сбой"))
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=forbidden_retriever,
        handoff_classifier=_classifier(raises=True),
    )
    result = await graph.ainvoke(_state(text="Соедините с живым специалистом"))
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == DETECTOR_FAILURE_REASON
    llm_mock.generate.assert_not_called()


async def test_handoff_classifier_disabled_uses_gigachat(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    """Ключ OpenRouter не задан — детект идёт через GigaChat Lite."""
    llm_mock.classify_handoff = AsyncMock(return_value=True)
    classifier = _classifier("HANDOFF")
    classifier.is_configured.return_value = False
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=classifier,
    )
    result = await graph.ainvoke(_state(text="Соедините с живым специалистом"))
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    classifier.route.assert_not_awaited()
    llm_mock.classify_handoff.assert_awaited_once()
    llm_mock.generate.assert_not_called()


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


async def test_run_chat_turn_vision_keeps_guest_text(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    cache_mocks: tuple[AsyncMock, AsyncMock],
    db_session: AsyncSession,
) -> None:
    """Скриншот: гость видит ответ, в ленте его текст, не дамп Vision."""
    from sqlalchemy import select

    import app.services.agent as agent_service
    from app.core.config import settings
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message

    monkeypatch.setattr(settings, "operator_assist_mode", "auto")
    llm_mock.chat_with_vision = AsyncMock(return_value="Интерфейс Telegram")
    llm_mock.generate = AsyncMock(return_value="На скрине Telegram, не ошибка 1С.")
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_empty_retriever,
        handoff_classifier=_classifier(),
    )
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)
    request = chat_request.model_copy(
        update={"text": "что видишь?", "image_base64": "AAA"}
    )
    response = await run_chat_turn(request, db_session)
    assert response.escalated is False
    assert response.text == "На скрине Telegram, не ошибка 1С."

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.OPEN

    user_rows = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == response.conversation_id,
                    Message.role == MessageRole.USER,
                )
            )
        ).all()
    )
    assert user_rows[0].content == "что видишь?"


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


async def test_run_chat_turn_handoff_persists_reason(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import select

    import app.services.agent as agent_service
    from app.models.enums import ConversationStatus
    from app.models.escalation import Escalation

    graph = build_graph(
        llm_mock,
        app_settings,
        handoff_classifier=_classifier("HANDOFF"),
    )
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    request = chat_request.model_copy(update={"text": "Позовите оператора"})
    response = await run_chat_turn(request, db_session)

    assert response.escalated is True
    assert "оператор" in response.text
    assert response.sources == []

    escalation = (
        await db_session.scalars(
            select(Escalation).where(
                Escalation.conversation_id == response.conversation_id
            )
        )
    ).first()
    assert escalation is not None
    assert escalation.reason == HANDOFF_ESCALATION_REASON
    assert escalation.escalated_to == "operator"

    from app.models.conversation import Conversation

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED


async def test_run_chat_turn_handoff_replay_does_not_double_escalate(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    """Повтор «позовите оператора» не создаёт второй тикет."""
    from sqlalchemy import func, select

    import app.services.agent as agent_service
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus
    from app.models.escalation import Escalation

    graph = build_graph(
        llm_mock,
        app_settings,
        handoff_classifier=_classifier("HANDOFF"),
    )
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    request = chat_request.model_copy(update={"text": "Позовите оператора"})
    first = await run_chat_turn(request, db_session)
    replay = request.model_copy(
        update={
            "conversation_id": first.conversation_id,
            "message_id": uuid4(),
        }
    )
    await run_chat_turn(replay, db_session)

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
    from app.services.conversations import IMAGE_HOLD_TEXT

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
    assert rows[-1].content == IMAGE_HOLD_TEXT
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


async def test_force_handoff_skips_router_classifier() -> None:
    classifier = _classifier()
    llm = _llm(handoff=False)
    result = await route_intent(
        {"query": "Позовите оператора", "force_handoff": True},
        classifier=classifier,
        llm=llm,
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result["escalation_reason"] == HANDOFF_ESCALATION_REASON
    classifier.route.assert_not_awaited()
    llm.classify_handoff.assert_not_awaited()


async def test_force_handoff_graph_skips_retrieve_and_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    classifier = _classifier()
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=classifier,
    )
    result = await graph.ainvoke(_state(force_handoff=True, text="Позовите оператора"))
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    classifier.route.assert_not_awaited()
    llm_mock.classify_handoff.assert_not_awaited()
    llm_mock.generate.assert_not_called()


async def test_force_handoff_empty_text_escalates_not_empty_template(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    classifier = _classifier()
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=classifier,
    )
    result = await graph.ainvoke(
        _state(force_handoff=True, text=None, image_base64=None)
    )
    assert result["intent"] == "handoff"
    assert result["escalated"] is True
    assert result.get("answer") != _EMPTY_REPLY
    classifier.route.assert_not_awaited()
    llm_mock.generate.assert_not_called()


async def test_ordinary_message_still_runs_router_classifier(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    classifier = _classifier()
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=classifier,
    )
    result = await graph.ainvoke(_state(force_handoff=False))
    assert result["intent"] == "support"
    classifier.route.assert_awaited_once()
    llm_mock.generate.assert_awaited_once()


async def test_run_chat_turn_force_handoff_persists_one_escalation(
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

    classifier = _classifier()
    graph = build_graph(
        llm_mock,
        app_settings,
        retriever=_hit_retriever,
        handoff_classifier=classifier,
    )
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    request = chat_request.model_copy(
        update={"text": "Позовите оператора", "force_handoff": True}
    )
    first = await run_chat_turn(request, db_session)
    assert first.escalated is True
    assert first.text == GUEST_ESCALATION_TEXT
    classifier.route.assert_not_awaited()
    llm_mock.generate.assert_not_called()

    replay = request.model_copy(
        update={
            "conversation_id": first.conversation_id,
            "message_id": uuid4(),
        }
    )
    await run_chat_turn(replay, db_session)

    conversation = await db_session.get(Conversation, first.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    count = await db_session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.conversation_id == first.conversation_id)
    )
    assert count == 1
    reason = (
        await db_session.scalars(
            select(Escalation.reason).where(
                Escalation.conversation_id == first.conversation_id
            )
        )
    ).first()
    assert reason == HANDOFF_ESCALATION_REASON


async def test_draft_open_high_score_answers_guest(
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
    from app.models.enums import MessageRole
    from app.models.message import Message

    llm_mock.generate = AsyncMock(return_value="Ответ из базы")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.escalated is False
    assert response.text == "Ответ из базы"
    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == response.conversation_id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 1


async def test_agent_high_score_holds_draft_not_guest_answer(
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
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.escalation import Escalation
    from app.models.message import Message

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.escalated is True
    assert response.text == GUEST_ESCALATION_TEXT
    llm_mock.generate.assert_awaited()

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Ответ из базы"

    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 0
    system_rows = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.SYSTEM,
                )
            )
        ).all()
    )
    assert [row.content for row in system_rows] == [GUEST_ESCALATION_TEXT]
    escalation = (
        await db_session.scalars(
            select(Escalation).where(Escalation.conversation_id == conversation.id)
        )
    ).first()
    assert escalation is not None
    assert escalation.reason == AGENT_HOLD_REASON


async def test_agent_weak_score_fills_draft_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    import app.services.agent as agent_service
    import app.services.channel_handoff as channel_handoff
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    generate_draft = AsyncMock(return_value="Черновик после слабого скора")
    monkeypatch.setattr(channel_handoff, "generate_draft", generate_draft)
    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.escalated is True
    llm_mock.generate.assert_not_called()
    generate_draft.assert_awaited_once()

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Черновик после слабого скора"


async def test_agent_weak_score_keeps_status_if_draft_fails(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
    db_session: AsyncSession,
) -> None:
    import app.services.agent as agent_service
    import app.services.channel_handoff as channel_handoff
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(side_effect=RuntimeError("gigachat down")),
    )
    graph = build_graph(llm_mock, app_settings, retriever=_empty_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.escalated is True
    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response is None


async def test_agent_followup_updates_suggested_response(
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
    import app.services.channel_handoff as channel_handoff
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    llm_mock.generate = AsyncMock(return_value="Первый ответ")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    first = await run_chat_turn(chat_request, db_session)
    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен вызываться")),
    )
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(return_value="Второй черновик"),
    )
    replay = chat_request.model_copy(
        update={
            "conversation_id": first.conversation_id,
            "message_id": uuid4(),
            "text": "уточнение",
        }
    )
    second = await run_chat_turn(replay, db_session)
    assert second.escalated is True
    assert second.text == GUEST_ESCALATION_TEXT

    conversation = await db_session.get(Conversation, first.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Второй черновик"
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


def test_agent_empty_answer_holds_even_at_high_score() -> None:
    from app.schemas.chat import Source

    decision = apply_operator_reply_policy(
        mode="agent",
        intent="support",
        graph_escalated=False,
        answer="",
        sources=[
            Source(
                document_id=UUID(int=1),
                title="Инструкция",
                chunk_text="провести",
            )
        ],
        graph_escalation_reason="",
    )
    assert decision.escalated is True
    assert decision.guest_text == GUEST_ESCALATION_TEXT
    assert decision.suggested_response is None
    assert decision.persist_sources == []


async def test_agent_high_score_empty_answer_escalates_without_model_text(
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
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.message import Message

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    llm_mock.generate = AsyncMock(return_value="")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request, db_session)
    assert response.escalated is True
    assert response.text == GUEST_ESCALATION_TEXT

    conversation = await db_session.get(Conversation, response.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response is None
    assistant_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant_count == 0
    system_rows = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.SYSTEM,
                )
            )
        ).all()
    )
    assert [row.content for row in system_rows] == [GUEST_ESCALATION_TEXT]


async def test_force_handoff_on_escalated_agent_keeps_draft(
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
    import app.services.channel_handoff as channel_handoff
    from app.models.conversation import Conversation
    from app.models.enums import ConversationStatus, MessageRole
    from app.models.escalation import Escalation
    from app.models.message import Message

    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    llm_mock.generate = AsyncMock(return_value="Первый ответ")
    graph = build_graph(llm_mock, app_settings, retriever=_hit_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    first = await run_chat_turn(chat_request, db_session)
    generate_draft = AsyncMock(return_value="не должен")
    monkeypatch.setattr(channel_handoff, "generate_draft", generate_draft)
    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф не должен вызываться")),
    )
    replay = chat_request.model_copy(
        update={
            "conversation_id": first.conversation_id,
            "message_id": uuid4(),
            "text": "Позовите оператора",
            "force_handoff": True,
        }
    )
    second = await run_chat_turn(replay, db_session)
    assert second.escalated is True
    assert second.text == GUEST_ESCALATION_TEXT
    generate_draft.assert_not_awaited()

    conversation = await db_session.get(Conversation, first.conversation_id)
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Первый ответ"
    count = await db_session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.conversation_id == first.conversation_id)
    )
    assert count == 1
    user_count = await db_session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.USER,
        )
    )
    assert user_count == 2
