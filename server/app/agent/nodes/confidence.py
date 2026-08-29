"""Оценка уверенности ответа отдельным запросом к GigaChat."""

from app.agent.parsing import parse_confidence
from app.agent.prompts import CONFIDENCE_PROMPT
from app.agent.state import AgentState, RetrievedChunk
from app.core.gigachat_client import GigaChatService


async def confidence_check(
    state: AgentState, *, llm: GigaChatService
) -> dict[str, float]:
    """Просит модель оценить ответ по шкале 0..1."""
    context = _format_chunks(state.get("chunks") or [])
    raw = await llm.generate(
        [
            {
                "role": "user",
                "content": CONFIDENCE_PROMPT.format(
                    query=state.get("query") or "",
                    context=context,
                    answer=state.get("answer") or "",
                ),
            }
        ]
    )
    return {"confidence": parse_confidence(raw)}


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "нет"
    return "\n\n".join(f"[{item['title']}]\n{item['chunk_text']}" for item in chunks)
