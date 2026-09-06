"""Классификация обращения: пусто или вопрос в поддержку."""

import logging

from app.agent.state import AgentState
from app.core.logging import preview

logger = logging.getLogger(__name__)

_EMPTY_REPLY = "Опишите проблему текстом или приложите скриншот ошибки 1С."


async def classify(state: AgentState) -> dict[str, object]:
    """Определяет intent по правилам (без LLM). Пустой запрос — сразу шаблон.

    Всё остальное — including приветствия и явный оффтоп — идёт в support:
    ответ всегда формирует GigaChat, никаких заготовок вместо вызова LLM.
    """
    query = (state.get("query") or "").strip()
    if not query:
        logger.info("classify intent=empty")
        return {
            "query": "",
            "intent": "empty",
            "answer": _EMPTY_REPLY,
            "confidence": 1.0,
            "escalated": False,
        }

    logger.info("classify intent=support query=%s", preview(query))
    return {"query": query, "intent": "support"}
