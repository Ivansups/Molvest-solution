"""Классификация обращения: приветствие, явный оффтоп или вопрос в поддержку."""

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
    r"\b(привет|здравствуй|здравствуйте|спасибо|пожалуйста|добрый|доброе|доброе утро|"
    r"добрый день|добрый вечер|пока|до свидания|hello|hi|thanks|bye)\b"
)

# Только левая граница слова: элементы — основы, а не целые слова, поэтому
# закрывающий \b обрезал бы «ошибка», «настройки», «зарплата» и т.п.
_SUPPORT_RE = (
    r"\b(1с|учёт|учет|систем|конфигурац|ошибк|проблем|"
    r"не работа|не запуска|не открывается|не записывает|не проводит|"
    r"документ|справочник|отчёт|отчет|настройк|обновлен|регистр|"
    r"запрос|блокировк|права|роль|erp|бухгалтер|"
    r"калькуляц|себестоимост|зарплат|кадр|"
    r"сервер|баз[аыуе]|лиценз|клиент|rdp|терминал|публикац)"
)

_OFF_TOPIC_RE = (
    r"\b(погод[аыуе]|футбол|анекдот|шутк|политик|курс\s*доллар|"
    r"натурал|секс|любов|рецепт|кино|сериал)\b"
)


def _canned(query: str, intent: str, answer: str) -> dict[str, object]:
    return {
        "query": query,
        "intent": intent,
        "answer": answer,
        "confidence": 1.0,
        "escalated": False,
    }


async def classify(state: AgentState) -> dict[str, object]:
    """Определяет intent по правилам (без LLM).

    Порядок: пусто → support-ключевые → приветствие → явный оффтоп → иначе support.
    """
    query = (state.get("query") or "").strip()
    if not query:
        logger.info("classify intent=empty")
        return _canned("", "empty", _EMPTY_REPLY)

    lower = query.lower()
    if re.search(_SUPPORT_RE, lower):
        logger.info("classify intent=support query=%s", preview(query))
        return {"query": query, "intent": "support"}

    if re.search(_GREETING_RE, lower):
        logger.info("classify intent=greeting query=%s", preview(query))
        return _canned(query, "greeting", _GREETING_REPLY)

    if re.search(_OFF_TOPIC_RE, lower):
        logger.info("classify intent=off_topic query=%s", preview(query))
        return _canned(query, "off_topic", _OFF_TOPIC_REPLY)

    logger.info("classify intent=support (default) query=%s", preview(query))
    return {"query": query, "intent": "support"}
