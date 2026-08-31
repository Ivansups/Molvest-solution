"""Классификация обращения: приветствие, не по теме или вопрос по 1С."""

from app.agent.state import AgentState

_EMPTY_REPLY = "Опишите проблему текстом или приложите скриншот ошибки 1С."

_GREETING_RE = (
    r"\b(привет|здравствуй|спасибо|пожалуйста|добрый|доброе|доброе утро|"
    r"добрый день|добрый вечер|пока|до свидания| hail|hello|hi|thanks|bye)\b"
)

_SUPPORT_RE = (
    r"\b(1с|1с[-\s]?ursed|учёт|учет|система|конфигурация|ошибк|проблем|"
    r"не работа|не запуска|не открывается|не записывает|не проводит|"
    r"документ|справочник|отчёт|отчет|настройк|обновлен|регистр|"
    r"запрос|блокировк|права|роль|interfacedrive|erp|бухгалтер|"
    r"калькуляц|себестоимост|зарплат|кадр|inventory|ufenpflege)\b"
)


async def classify(state: AgentState, *, llm: object = None) -> dict[str, object]:  # noqa: ARG001
    """Определяет intent по правилам (без LLM)."""
    import re

    query = (state.get("query") or "").strip()
    if not query:
        return {
            "query": "",
            "intent": "empty",
            "answer": _EMPTY_REPLY,
            "confidence": 1.0,
            "escalated": False,
        }

    lower = query.lower()
    if re.search(_GREETING_RE, lower):
        intent = "greeting"
    elif re.search(_SUPPORT_RE, lower):
        intent = "support"
    else:
        intent = "off_topic"

    return {"query": query, "intent": intent}
