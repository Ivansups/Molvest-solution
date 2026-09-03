"""Генерация ответа эксперта 1С по вопросу и найденному контексту."""

import logging

from app.agent.prompts import GENERATE_SYSTEM_PROMPT
from app.agent.state import AgentState, HistoryTurn, RetrievedChunk
from app.core.gigachat_client import ChatTurn, GigaChatService
from app.core.logging import preview

logger = logging.getLogger(__name__)


async def generate(state: AgentState, *, llm: GigaChatService) -> dict[str, object]:
    """Пишет ответ по вопросу, истории и найденным чанкам."""
    query = state.get("query") or ""
    chunks = state.get("chunks") or []
    history = state.get("history") or []

    messages: list[ChatTurn] = [
        {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _user_prompt(query, chunks, history),
        },
    ]
    logger.info(
        "generate вызов chunks=%s history=%s",
        len(chunks),
        len(history),
    )
    answer = await llm.generate(messages)
    logger.info("generate ответ chars=%s text=%s", len(answer), preview(answer))
    confidence = max((c["score"] for c in chunks), default=0.0)
    return {"answer": answer, "confidence": confidence}


def _user_prompt(
    query: str,
    chunks: list[RetrievedChunk],
    history: list[HistoryTurn],
) -> str:
    parts: list[str] = []
    if history:
        lines = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history)
        parts.append(f"Предыдущие сообщения:\n{lines}")
    parts.append(f"Вопрос:\n{query}")
    if chunks:
        context = "\n\n".join(
            f"[{item['title']}]\n{item['chunk_text']}" for item in chunks
        )
        parts.append(f"Фрагменты базы знаний:\n{context}")
    else:
        parts.append("Фрагменты базы знаний: нет.")
    return "\n\n".join(parts)
