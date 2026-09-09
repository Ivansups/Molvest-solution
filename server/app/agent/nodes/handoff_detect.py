"""Детект явной просьбы о хэндоффе лёгкой LLM (OpenRouter)."""

import logging

from app.agent.state import AgentState
from app.core.logging import preview
from app.core.openrouter_client import OpenRouterClassifier, OpenRouterError

logger = logging.getLogger(__name__)

# Причина эскалации по явной просьбе гостя — видна оператору в тикете.
HANDOFF_ESCALATION_REASON = "Явный запрос передачи оператору"


async def handoff_detect(
    state: AgentState,
    *,
    classifier: OpenRouterClassifier,
) -> dict[str, object]:
    """Классифицирует запрос и эскалирует, если гость просит передать человеку.

    Сбой или неожиданный ответ классификатора — фолбэк в `support`: граф идёт
    дальше по обычному пути, чат не роняем. Пустой/не заданный ключ — детект
    пропускается (узел ничего не меняет).
    """
    query = (state.get("query") or "").strip()
    if not query or not classifier.is_configured():
        return {}

    try:
        handoff = await classifier.is_handoff_request(query)
    except OpenRouterError as exc:
        logger.warning(
            "handoff_detect сбой, фолбэк в support query=%s (%s)",
            preview(query),
            exc,
        )
        return {}

    if handoff:
        logger.info("handoff_detect запрос хэндоффа query=%s", preview(query))
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }

    return {}
