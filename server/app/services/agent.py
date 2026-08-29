"""Запуск диалогового графа для одного сообщения чата."""

from uuid import UUID, uuid4

from app.agent.graph import get_graph
from app.agent.state import AgentState, RetrievedChunk
from app.schemas.chat import ChatRequest, ChatResponse, Source


async def run_chat_turn(request: ChatRequest) -> ChatResponse:
    """Прогоняет запрос через LangGraph и мапит состояние в контракт /chat."""
    final = await get_graph().ainvoke(_initial_state(request))
    return ChatResponse(
        conversation_id=request.conversation_id or uuid4(),
        message_id=request.message_id,
        text=final.get("answer") or "",
        confidence=final.get("confidence", 0.0),
        escalated=final.get("escalated", False),
        sources=_to_sources(final.get("chunks") or []),
    )


def _initial_state(request: ChatRequest) -> AgentState:
    return {
        "text": request.text,
        "image_base64": request.image_base64,
        "query": "",
        "intent": "empty",
        "chunks": [],
        "answer": "",
        "confidence": 0.0,
        "escalated": False,
    }


def _to_sources(chunks: list[RetrievedChunk]) -> list[Source]:
    sources: list[Source] = []
    for chunk in chunks:
        sources.append(
            Source(
                document_id=UUID(chunk["document_id"]),
                title=chunk["title"],
                chunk_text=chunk["chunk_text"],
            )
        )
    return sources
