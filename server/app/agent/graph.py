"""Сборка графа: vision → classify → router → кэш / RAG / ответ."""

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.generate import generate
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.router import route_intent
from app.agent.nodes.vision import vision
from app.agent.state import AgentState
from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService, get_gigachat_service
from app.core.openrouter_client import OpenRouterClassifier, get_openrouter_classifier
from app.core.redis import get_cached_answer, get_kb_version, set_cached_answer
from app.rag.retrieval import Retriever, make_retriever

logger = logging.getLogger(__name__)


def _timed[NodeT: Callable[[AgentState], Awaitable[Mapping[str, object]]]](
    name: str, node: NodeT
) -> NodeT:
    """Оборачивает ноду замером времени: видно вклад каждого шага в общий p95/p99."""

    async def wrapper(state: AgentState) -> Mapping[str, object]:
        started = time.monotonic()
        result = await node(state)
        elapsed_ms = (time.monotonic() - started) * 1000
        logger.info("node timing name=%s ms=%.1f", name, elapsed_ms)
        return result

    return cast(NodeT, wrapper)


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

    async def router_node(state: AgentState) -> dict[str, object]:
        return await route_intent(state, classifier=effective_classifier, llm=llm)

    builder.add_node("vision", _timed("vision", vision_node))
    builder.add_node("classify", _timed("classify", classify))
    builder.add_node("router", _timed("router", router_node))
    builder.add_node("lookup_cache", _timed("lookup_cache", _lookup_cached_answer))
    builder.add_node("retrieve", _timed("retrieve", retrieve_node))
    builder.add_node("generate", _timed("generate", generate_node))

    builder.add_edge(START, "vision")
    builder.add_edge("vision", "classify")
    builder.add_conditional_edges("classify", _after_classify)
    builder.add_conditional_edges("router", _after_router)
    builder.add_conditional_edges("lookup_cache", _after_cache)

    def after_retrieve(state: AgentState) -> Literal["generate", "__end__"]:
        nxt: Literal["generate", "__end__"] = (
            "__end__" if state.get("escalated") else "generate"
        )
        logger.info(
            "после retrieve chunks=%s confidence=%s escalated=%s → %s",
            len(state.get("chunks") or []),
            state.get("confidence"),
            state.get("escalated"),
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
) -> Literal["router", "__end__"]:
    if state.get("force_handoff"):
        logger.info("после classify force_handoff → router")
        return "router"
    intent = state.get("intent", "support")
    nxt: Literal["router", "__end__"] = "__end__" if intent == "empty" else "router"
    logger.info("после classify intent=%s → %s", intent, nxt)
    return nxt


def _after_router(
    state: AgentState,
) -> Literal["lookup_cache", "__end__"]:
    """Роутер закончил диалог (оффтоп/приветствие/эскалация) или идём в кэш."""
    ended = bool(state.get("answer")) or bool(state.get("escalated"))
    nxt: Literal["lookup_cache", "__end__"] = "__end__" if ended else "lookup_cache"
    logger.info(
        "после router intent=%s answer=%s escalated=%s → %s",
        state.get("intent"),
        bool(state.get("answer")),
        state.get("escalated"),
        nxt,
    )
    return nxt


def _after_cache(state: AgentState) -> Literal["retrieve", "__end__"]:
    return "__end__" if state.get("answer") else "retrieve"


_graph: CompiledStateGraph[AgentState, None] | None = None
