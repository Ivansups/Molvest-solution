"""Ретривал чанков: поиск по базе знаний через внедрённый ретривер."""

import logging

from app.agent.state import AgentState
from app.core.config import settings
from app.rag.retrieval import Retriever

logger = logging.getLogger(__name__)


async def retrieve(
    state: AgentState,
    *,
    retriever: Retriever,
) -> dict[str, object]:
    """Возвращает релевантные чанки и оценку уверенности по скору ретривала."""
    chunks = await retriever(state)
    confidence = max((c["score"] for c in chunks), default=0.0)
    logger.info(
        "retrieve chunks=%s confidence=%s escalated=%s",
        len(chunks),
        confidence,
        confidence < settings.confidence_threshold,
    )
    return {
        "chunks": chunks,
        "confidence": confidence,
        "escalated": confidence < settings.confidence_threshold,
    }
