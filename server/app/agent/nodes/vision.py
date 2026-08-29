"""Входной узел: скриншот → текстовое описание для общего RAG-пути."""

from app.agent.prompts import VISION_PROMPT
from app.agent.state import AgentState
from app.core.gigachat_client import GigaChatService


async def vision(state: AgentState, *, llm: GigaChatService) -> dict[str, str]:
    """Собирает query из текста и, если есть картинка, из Vision."""
    query = (state.get("text") or "").strip()
    image_base64 = state.get("image_base64")
    if not image_base64:
        return {"query": query}

    description = await llm.chat_with_vision(image_base64, VISION_PROMPT)
    if query:
        query = f"{query}\n\nОписание скриншота:\n{description}"
    else:
        query = description
    return {"query": query}
