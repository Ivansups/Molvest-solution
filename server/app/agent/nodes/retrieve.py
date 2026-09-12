"""Ретривал чанков: поиск по базе знаний через внедрённый ретривер."""

import logging

from app.agent.state import AgentState
from app.rag.retrieval import Retriever
from app.services.runtime_settings import get_effective_confidence_threshold

logger = logging.getLogger(__name__)


async def retrieve(
    state: AgentState,
    *,
    retriever: Retriever,
) -> dict[str, object]:
    """Возвращает релевантные чанки и оценку уверенности по скору ретривала."""
    chunks = await retriever(state)
    confidence = max((c["score"] for c in chunks), default=0.0)
    threshold = get_effective_confidence_threshold()
    # Скриншот уже разобран Vision: слабый поиск не должен прятать ответ.
    escalate = confidence < threshold and not state.get("image_base64")
    logger.info(
        "retrieve chunks=%s confidence=%s image=%s escalated=%s",
        len(chunks),
        confidence,
        bool(state.get("image_base64")),
        escalate,
    )
    return {
        "chunks": chunks,
        "confidence": confidence,
        "escalated": escalate,
    }
