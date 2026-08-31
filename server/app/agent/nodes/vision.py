"""Входной узел: скриншот → текстовое описание для общего RAG-пути."""

import logging

from app.agent.prompts import VISION_PROMPT
from app.agent.state import AgentState
from app.core.gigachat_client import GigaChatService
from app.core.logging import preview

logger = logging.getLogger(__name__)


async def vision(state: AgentState, *, llm: GigaChatService) -> dict[str, str]:
    """Собирает query из текста и, если есть картинка, из Vision."""
    query = (state.get("text") or "").strip()
    image_base64 = state.get("image_base64")
    if not image_base64:
        logger.info("vision пропуск нет картинки")
        return {"query": query}

    logger.info("vision вызов image_chars=%s", len(image_base64))
    description = await llm.chat_with_vision(image_base64, VISION_PROMPT)
    logger.info(
        "vision описание chars=%s text=%s",
        len(description),
        preview(description),
    )
    if query:
        query = f"{query}\n\nОписание скриншота:\n{description}"
    else:
        query = description
    return {"query": query}
