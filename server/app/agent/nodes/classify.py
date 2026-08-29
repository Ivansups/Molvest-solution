"""Классификация обращения: приветствие, не по теме или вопрос по 1С."""

from app.agent.parsing import parse_intent
from app.agent.prompts import CLASSIFY_PROMPT
from app.agent.state import AgentState
from app.core.gigachat_client import GigaChatService

_EMPTY_REPLY = "Опишите проблему текстом или приложите скриншот ошибки 1С."


async def classify(state: AgentState, *, llm: GigaChatService) -> dict[str, object]:
    """Определяет intent. Пустой ввод не отправляем в модель."""
    query = (state.get("query") or "").strip()
    if not query:
        return {
            "query": "",
            "intent": "empty",
            "answer": _EMPTY_REPLY,
            "confidence": 1.0,
            "escalated": False,
        }

    raw = await llm.generate(
        [{"role": "user", "content": CLASSIFY_PROMPT.format(query=query)}]
    )
    return {"query": query, "intent": parse_intent(raw)}
