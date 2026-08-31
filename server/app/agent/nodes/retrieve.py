"""Ретривал чанков: поиск по базе знаний через внедрённый ретривер."""

from app.agent.state import AgentState, RetrievedChunk
from app.rag.retrieval import Retriever


async def retrieve(
    state: AgentState,
    *,
    retriever: Retriever,
) -> dict[str, list[RetrievedChunk]]:
    """Возвращает релевантные чанки, найденные ретривером."""
    chunks = await retriever(state)
    return {"chunks": chunks}
