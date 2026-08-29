"""Сборка диалогового графа: vision → classify → RAG / короткий ответ."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.classify import classify
from app.agent.nodes.confidence import confidence_check
from app.agent.nodes.generate import generate
from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.route import route
from app.agent.nodes.vision import vision
from app.agent.state import AgentState
from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService, get_gigachat_service


def build_graph(
    llm: GigaChatService,
    app_settings: Settings,
) -> CompiledStateGraph[AgentState, None]:
    """Собирает стартовый граф сценариев 1–3."""
    builder: StateGraph[AgentState, None] = StateGraph(AgentState)

    async def vision_node(state: AgentState) -> dict[str, str]:
        return await vision(state, llm=llm)

    async def classify_node(state: AgentState) -> dict[str, object]:
        return await classify(state, llm=llm)

    async def generate_node(state: AgentState) -> dict[str, object]:
        return await generate(state, llm=llm)

    async def confidence_node(state: AgentState) -> dict[str, float]:
        return await confidence_check(state, llm=llm)

    async def retrieve_node(state: AgentState) -> dict[str, object]:
        return await retrieve(state)

    async def route_node(state: AgentState) -> dict[str, bool]:
        return await route(state, settings=app_settings)

    builder.add_node("vision", vision_node)
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_node("confidence_check", confidence_node)
    builder.add_node("route", route_node)

    builder.add_edge(START, "vision")
    builder.add_edge("vision", "classify")
    builder.add_conditional_edges("classify", _after_classify)
    builder.add_edge("retrieve", "generate")
    builder.add_conditional_edges("generate", _after_generate)
    builder.add_edge("confidence_check", "route")
    builder.add_edge("route", END)
    return builder.compile()


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
        return "__end__"
    if intent in ("greeting", "off_topic"):
        return "generate"
    return "retrieve"


def _after_generate(state: AgentState) -> Literal["confidence_check", "__end__"]:
    if state.get("intent") == "support":
        return "confidence_check"
    return "__end__"


_graph: CompiledStateGraph[AgentState, None] | None = None
