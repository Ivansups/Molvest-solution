"""Сборка диалогового графа: vision → classify → handoff → кэш / RAG / ответ."""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.generate import generate
from app.agent.nodes.handoff_detect import handoff_detect
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.vision import vision
from app.agent.state import AgentState
from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService, get_gigachat_service
from app.core.openrouter_client import OpenRouterClassifier, get_openrouter_classifier
from app.core.redis import get_cached_answer, get_kb_version, set_cached_answer
from app.rag.retrieval import Retriever, make_retriever
from app.services.runtime_settings import get_effective_confidence_threshold

logger = logging.getLogger(__name__)


def build_graph(
    llm: GigaChatService,
    app_settings: Settings,
    *,
    retriever: Retriever | None = None,
    handoff_classifier: OpenRouterClassifier | None = None,
) -> CompiledStateGraph[AgentState, None]:
    """Собирает стартовый граф сценариев 1–3."""
    effective_retriever = retriever or make_retriever(llm, app_settings)
    effective_classifier = handoff_classifier or get_openrouter_classifier()
    builder: StateGraph[AgentState, None] = StateGraph(AgentState)

    async def vision_node(state: AgentState) -> dict[str, str]:
        return await vision(state, llm=llm)

    async def generate_node(state: AgentState) -> dict[str, object]:
        return await _generate_and_cache(state, llm=llm)

    async def retrieve_node(state: AgentState) -> dict[str, object]:
        return await retrieve(state, retriever=effective_retriever)

    async def handoff_detect_node(state: AgentState) -> dict[str, object]:
        return await handoff_detect(state, classifier=effective_classifier)

    builder.add_node("vision", vision_node)
    builder.add_node("classify", classify)
    builder.add_node("handoff_detect", handoff_detect_node)
    builder.add_node("lookup_cache", _lookup_cached_answer)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "vision")
    builder.add_edge("vision", "classify")
    builder.add_conditional_edges("classify", _after_classify)
    builder.add_conditional_edges("handoff_detect", _after_handoff_detect)
    builder.add_conditional_edges("lookup_cache", _after_cache)

    def after_retrieve(state: AgentState) -> Literal["generate", "__end__"]:
        chunks = state.get("chunks") or []
        confidence = max((c["score"] for c in chunks), default=0.0)
        threshold = get_effective_confidence_threshold()
        nxt: Literal["generate", "__end__"] = (
            "__end__" if confidence < threshold else "generate"
        )
        logger.info(
            "после retrieve chunks=%s confidence=%s threshold=%s → %s",
            len(chunks),
            confidence,
            threshold,
            nxt,
        )
        return nxt

    builder.add_conditional_edges("retrieve", after_retrieve)
    builder.add_edge("generate", END)
    return builder.compile()


def _cache_scope(state: AgentState) -> str | None:
    """Инсталляция, в которой ход можно кэшировать, иначе None.

    Кэш общий для всех пользователей инсталляции и ключуется текстом вопроса,
    поэтому ход с историей диалога в него не попадает: такой ответ осмыслен
    только внутри своего диалога.
    """
    installation_id = state.get("installation_id")
    if not installation_id or state.get("history"):
        return None
    return installation_id


async def _lookup_cached_answer(state: AgentState) -> dict[str, object]:
    """Читает кэш ответа до retrieve, попутно фиксируя версию БЗ в состоянии."""
    scope = _cache_scope(state)
    if scope is None:
        return {}
    query = state.get("query") or ""
    kb_ver = await get_kb_version()
    cached = await get_cached_answer(query, kb_ver, scope)
    if cached is None:
        logger.info("кэш ответа промах kb_version=%s", kb_ver)
        return {"kb_version": kb_ver}
    logger.info("кэш ответа попадание kb_version=%s", kb_ver)
    return {
        "answer": cached["answer"],
        "chunks": cached["chunks"],
        "confidence": 1.0,
        "escalated": False,
    }


async def _generate_and_cache(
    state: AgentState, llm: GigaChatService
) -> dict[str, object]:
    """Генерация и запись кэша. Сюда попадаем только без эскалации."""
    result = await generate(state, llm=llm)
    answer = result.get("answer")
    query = state.get("query") or ""
    scope = _cache_scope(state)
    if isinstance(answer, str) and answer and query and scope is not None:
        # версию БЗ уже прочитал lookup_cache — второй раз в Redis не ходим
        kb_ver = state["kb_version"]
        await set_cached_answer(
            query,
            answer,
            kb_ver,
            installation_id=scope,
            chunks=state.get("chunks") or [],
        )
        logger.info("кэш ответа записан kb_version=%s", kb_ver)
    return result


def get_graph() -> CompiledStateGraph[AgentState, None]:
    """Скомпилированный граф на процесс — клиент GigaChat один."""
    global _graph
    if _graph is None:
        _graph = build_graph(get_gigachat_service(), settings)
    return _graph


def _after_classify(
    state: AgentState,
) -> Literal["handoff_detect", "__end__"]:
    intent = state.get("intent", "support")
    nxt: Literal["handoff_detect", "__end__"] = (
        "__end__" if intent == "empty" else "handoff_detect"
    )
    logger.info("после classify intent=%s → %s", intent, nxt)
    return nxt


def _after_handoff_detect(
    state: AgentState,
) -> Literal["lookup_cache", "__end__"]:
    intent = state.get("intent", "support")
    nxt: Literal["lookup_cache", "__end__"] = (
        "__end__" if intent == "handoff" else "lookup_cache"
    )
    logger.info("после handoff_detect intent=%s → %s", intent, nxt)
    return nxt


def _after_cache(state: AgentState) -> Literal["retrieve", "__end__"]:
    return "__end__" if state.get("answer") else "retrieve"


_graph: CompiledStateGraph[AgentState, None] | None = None
