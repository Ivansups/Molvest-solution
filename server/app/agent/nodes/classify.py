"""Классификация обращения: пусто, вопрос в поддержку или хэндофф оператору."""

import logging
import re

from app.agent.state import AgentState
from app.core.logging import preview

logger = logging.getLogger(__name__)

_EMPTY_REPLY = "Опишите проблему текстом или приложите скриншот ошибки 1С."

# Причина эскалации по явной просьбе гостя — видна оператору в тикете.
HANDOFF_ESCALATION_REASON = "Явный запрос передачи оператору"

# Вопросы «как …», «можно ли …» про оператора — это запрос к базе знаний,
# а не просьба о хэндоффе: отсекаем их до проверки просьбы.
_HANDOFF_EXCLUSION = re.compile(
    r"^(?:как\w*|куда\b|зачем\w*|можно ли\b|есть ли\b|"
    r"подскажите\s+как\w*|расскажите\s+как\w*)\b",
    re.IGNORECASE,
)

# Императив «позовите/передайте/…» + адресат (оператор/специалист/человек).
_HANDOFF_REQUEST = re.compile(
    r"\b(?:позови|вызови|подключи|соедини|переключи|передай|пригласи|свяжи|"
    r"перевед)\w*\b[^\n]{0,40}"
    r"\b(?:оператор|специалист|человек|менеджер|сотрудник)\w*\b",
    re.IGNORECASE,
)

# «Нужен человек» / «хочу поговорить с человеком/оператором».
_HANDOFF_DESIRE = re.compile(
    r"\b(?:нужен|нужна|нужно|нужны)\b[^\n]{0,30}"
    r"\b(?:человек|оператор|специалист)\w*\b"
    r"|\bхоч\w*\b[^\n]{0,60}"
    r"\b(?:поговорить|говорить|общаться|разговаривать|связаться)\s+(?:с|со)\s+"
    r"(?:человек|оператор|специалист)\w*\b",
    re.IGNORECASE,
)


async def classify(state: AgentState) -> dict[str, object]:
    """Определяет intent по правилам (без LLM).

    Пустой запрос — сразу шаблон. Явная просьба передать диалог человеку
    («позовите оператора», «нужен человек») — хэндофф: граф эскалирует без
    retrieve/generate. Всё остальное — including приветствия и явный оффтоп —
    идёт в support: ответ всегда формирует GigaChat, никаких заготовок.
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

    if _is_handoff_request(query):
        logger.info("classify intent=handoff query=%s", preview(query))
        return {
            "query": query,
            "intent": "handoff",
            "escalated": True,
            "escalation_reason": HANDOFF_ESCALATION_REASON,
        }

    logger.info("classify intent=support query=%s", preview(query))
    return {"query": query, "intent": "support"}


def _is_handoff_request(query: str) -> bool:
    """Правда, если гость просит передать диалог человеку, а не факт про 1С."""
    if _HANDOFF_EXCLUSION.search(query):
        return False
    return bool(_HANDOFF_REQUEST.search(query) or _HANDOFF_DESIRE.search(query))
