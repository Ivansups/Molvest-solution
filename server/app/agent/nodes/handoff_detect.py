"""Детект явной просьбы о хэндоффе: OpenRouter, иначе GigaChat Lite."""

import logging

from app.agent.prompts import HANDOFF_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.core.gigachat_client import GigaChatError, GigaChatService
from app.core.logging import preview
from app.core.openrouter_client import OpenRouterClassifier, OpenRouterError

logger = logging.getLogger(__name__)

# Причина эскалации по явной просьбе гостя — видна оператору в тикете.
HANDOFF_ESCALATION_REASON = "Явный запрос передачи оператору"
# Классификатор недоступен: безопаснее тикет, чем автоответ из базы.
DETECTOR_FAILURE_REASON = "Сбой детекта передачи оператору"


async def handoff_detect(
    state: AgentState,
    *,
    classifier: OpenRouterClassifier,
    llm: GigaChatService,
) -> dict[str, object]:
    """Классифицирует запрос и эскалирует, если гость просит передать человеку.

    OpenRouter — основной классификатор. Пустой ключ или сбой OpenRouter —
    тот же YES/NO через GigaChat-2 (Lite). Сбой обоих — эскалация, не RAG.
    """
    if state.get("force_handoff"):
        logger.info("handoff_detect force_handoff без классификатора")
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }

    query = (state.get("query") or "").strip()
    if not query:
        return {}

    try:
        handoff = await _is_handoff(query, classifier=classifier, llm=llm)
    except (OpenRouterError, GigaChatError) as exc:
        logger.warning(
            "handoff_detect сбой, эскалация query=%s (%s)",
            preview(query),
            exc,
        )
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": DETECTOR_FAILURE_REASON,
        }

    if handoff:
        logger.info("handoff_detect запрос хэндоффа query=%s", preview(query))
        return {
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }

    return {}


async def _is_handoff(
    query: str,
    *,
    classifier: OpenRouterClassifier,
    llm: GigaChatService,
) -> bool:
    """YES от OpenRouter или, если его нет/он упал, от GigaChat Lite."""
    if classifier.is_configured():
        try:
            return await classifier.is_handoff_request(query)
        except OpenRouterError as exc:
            logger.warning(
                "OpenRouter сбой, фолбэк на GigaChat query=%s (%s)",
                preview(query),
                exc,
            )
    else:
        logger.info("OpenRouter не задан, классификация через GigaChat")
    return await llm.classify_handoff(query, system_prompt=HANDOFF_SYSTEM_PROMPT)
