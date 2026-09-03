"""Классификация обращения: приветствие, не по теме или вопрос по 1С."""

import logging
import re

from app.agent.state import AgentState
from app.core.logging import preview

logger = logging.getLogger(__name__)

_EMPTY_REPLY = "Опишите проблему текстом или приложите скриншот ошибки 1С."
_GREETING_REPLY = (
    "Здравствуйте! Опишите проблему по 1С — текстом или приложите скриншот."
)
_OFF_TOPIC_REPLY = (
    "Я помогаю только с вопросами по 1С и работе в учётной системе Молвест. "
    "Опишите проблему по 1С."
)

_GREETING_RE = (
    r"\b(привет|здравствуй|спасибо|пожалуйста|добрый|доброе|доброе утро|"
    r"добрый день|добрый вечер|пока|до свидания|hello|hi|thanks|bye)\b"
)

_SUPPORT_RE = (
    r"\b(1с|учёт|учет|система|конфигурация|ошибк|проблем|"
    r"не работа|не запуска|не открывается|не записывает|не проводит|"
    r"документ|справочник|отчёт|отчет|настройк|обновлен|регистр|"
    r"запрос|блокировк|права|роль|erp|бухгалтер|"
    r"калькуляц|себестоимост|зарплат|кадр)\b"
)


async def classify(state: AgentState, *, llm: object = None) -> dict[str, object]:  # noqa: ARG001
    """Определяет intent по правилам (без LLM). Support важнее приветствия."""
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

    lower = query.lower()
    if re.search(_SUPPORT_RE, lower):
        intent = "support"
        logger.info("classify intent=%s query=%s", intent, preview(query))
        return {"query": query, "intent": intent}

    if re.search(_GREETING_RE, lower):
        logger.info("classify intent=greeting query=%s", preview(query))
        return {
            "query": query,
            "intent": "greeting",
            "answer": _GREETING_REPLY,
            "confidence": 1.0,
            "escalated": False,
        }

    logger.info("classify intent=off_topic query=%s", preview(query))
    return {
        "query": query,
        "intent": "off_topic",
        "answer": _OFF_TOPIC_REPLY,
        "confidence": 1.0,
        "escalated": False,
    }
