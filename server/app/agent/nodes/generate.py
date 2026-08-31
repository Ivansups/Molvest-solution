"""Генерация ответа эксперта 1С по вопросу и найденному контексту."""

import logging

from app.agent.prompts import (
    GENERATE_GREETING_PROMPT,
    GENERATE_OFF_TOPIC_PROMPT,
    GENERATE_SYSTEM_PROMPT,
)
from app.agent.state import AgentState, RetrievedChunk
from app.core.gigachat_client import ChatTurn, GigaChatService
from app.core.logging import preview

logger = logging.getLogger(__name__)


async def generate(state: AgentState, *, llm: GigaChatService) -> dict[str, object]:
    """Пишет ответ. Для greeting/off_topic уверенность не проверяем."""
    query = state.get("query") or ""
    intent = state.get("intent", "support")
    chunks = state.get("chunks") or []

    extra = ""
    if intent == "greeting":
        extra = GENERATE_GREETING_PROMPT
    elif intent == "off_topic":
        extra = GENERATE_OFF_TOPIC_PROMPT

    messages: list[ChatTurn] = [
        {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _user_prompt(query, chunks, extra),
        },
    ]
    logger.info("generate вызов intent=%s chunks=%s", intent, len(chunks))
    answer = await llm.generate(messages)
    logger.info("generate ответ chars=%s text=%s", len(answer), preview(answer))

    if intent == "support":
        confidence = max((c["score"] for c in chunks), default=0.0)
        return {"answer": answer, "confidence": confidence}
    return {"answer": answer, "confidence": 1.0, "escalated": False}


def _user_prompt(query: str, chunks: list[RetrievedChunk], extra: str) -> str:
    parts = [f"Вопрос:\n{query}"]
    if extra:
        parts.append(extra)
    if chunks:
        context = "\n\n".join(
            f"[{item['title']}]\n{item['chunk_text']}" for item in chunks
        )
        parts.append(f"Фрагменты базы знаний:\n{context}")
    else:
        parts.append("Фрагменты базы знаний: нет.")
    return "\n\n".join(parts)
