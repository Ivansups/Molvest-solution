"""Ретривал чанков: поиск по базе знаний через внедрённый ретривер."""

from app.agent.state import AgentState
from app.core.config import settings
from app.rag.retrieval import Retriever


async def retrieve(
    state: AgentState,
    *,
    retriever: Retriever,
) -> dict[str, object]:
    """Возвращает релевантные чанки и оценку уверенности по скору ретривала."""
    chunks = await retriever(state)
    confidence = max((c["score"] for c in chunks), default=0.0)
    return {
        "chunks": chunks,
        "confidence": confidence,
        "escalated": confidence < settings.confidence_threshold,
    }
