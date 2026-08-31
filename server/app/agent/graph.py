"""Сборка диалогового графа: vision → classify → RAG / короткий ответ."""

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.generate import generate
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.vision import vision
from app.agent.state import AgentState
from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService, get_gigachat_service
from app.core.redis import get_cached_answer, get_kb_version, set_cached_answer
from app.rag.retrieval import Retriever, make_retriever

logger = logging.getLogger(__name__)


def build_graph(
    llm: GigaChatService,
    app_settings: Settings,
    *,
    retriever: Retriever | None = None,
) -> CompiledStateGraph[AgentState, None]:
    """Собирает стартовый граф сценариев 1–3."""
    effective_retriever = retriever or make_retriever(llm, app_settings)
    builder: StateGraph[AgentState, None] = StateGraph(AgentState)

    async def vision_node(state: AgentState) -> dict[str, str]:
        return await vision(state, llm=llm)

    async def classify_node(state: AgentState) -> dict[str, object]:
        return await classify(state)

    async def generate_node(state: AgentState) -> dict[str, object]:
        return await _cached_generate(state, llm=llm)

    async def retrieve_node(state: AgentState) -> dict[str, object]:
        return await retrieve(state, retriever=effective_retriever)

    builder.add_node("vision", vision_node)
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "vision")
    builder.add_edge("vision", "classify")
    builder.add_conditional_edges("classify", _after_classify)
    builder.add_conditional_edges("retrieve", _after_retrieve)
    builder.add_edge("generate", END)
    return builder.compile()


async def _cached_generate(
    state: AgentState, llm: GigaChatService
) -> dict[str, object]:
    """Генерация с кэшем ответов по версии БЗ."""
    query = state.get("query") or ""
    kb_ver = 0
    try:
        kb_ver = await get_kb_version()
        cached = await get_cached_answer(query, kb_ver)
    except Exception:
        logger.exception("кэш ответа недоступен")
        cached = None
    if cached is not None:
        logger.info("кэш ответа попадание kb_version=%s", kb_ver)
        return {"answer": cached}

    logger.info("кэш ответа промах kb_version=%s → generate", kb_ver)
    result = await generate(state, llm=llm)
    answer = result.get("answer") or ""
    if isinstance(answer, str) and answer:
        try:
            await set_cached_answer(query, answer, kb_ver)
            logger.info("кэш ответа записан kb_version=%s", kb_ver)
        except Exception:
            logger.exception("не удалось записать кэш ответа")
    return result


def get_graph() -> CompiledStateGraph[AgentState, None]:
    """Скомпилированный граф на процесс — клиент GigaChat один."""
    global _graph
    if _graph is None:
        _graph = build_graph(get_gigachat_service(), settings)
    return _graph


def _after_classify(
    state: AgentState,
) -> Literal["retrieve", "generate", "__end__"]:
    intent = state.get("intent", "support")
    if intent == "empty":
        nxt: Literal["retrieve", "generate", "__end__"] = "__end__"
    elif intent in ("greeting", "off_topic"):
        nxt = "generate"
    else:
        nxt = "retrieve"
    logger.info("после classify intent=%s → %s", intent, nxt)
    return nxt


def _after_retrieve(state: AgentState) -> Literal["generate", "__end__"]:
    chunks = state.get("chunks") or []
    confidence = max((c["score"] for c in chunks), default=0.0)
    nxt: Literal["generate", "__end__"] = (
        "__end__" if confidence < settings.confidence_threshold else "generate"
    )
    logger.info(
        "после retrieve chunks=%s confidence=%s threshold=%s → %s",
        len(chunks),
        confidence,
        settings.confidence_threshold,
        nxt,
    )
    return nxt


_graph: CompiledStateGraph[AgentState, None] | None = None
