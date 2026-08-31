"""Запуск диалогового графа для одного сообщения чата."""

import logging
from uuid import UUID, uuid4

from app.agent.graph import get_graph
from app.agent.state import AgentState, RetrievedChunk
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest, ChatResponse, Source

logger = logging.getLogger(__name__)


async def run_chat_turn(request: ChatRequest) -> ChatResponse:
    """Прогоняет запрос через LangGraph и мапит состояние в контракт /chat."""
    installation_id = workspace_to_installation_id(request.workspace_id)
    logger.info(
        "граф старт message_id=%s installation_id=%s",
        request.message_id,
        installation_id,
    )
    final = await get_graph().ainvoke(_initial_state(request, installation_id))
    logger.info(
        "граф конец message_id=%s intent=%s escalated=%s confidence=%s",
        request.message_id,
        final.get("intent"),
        final.get("escalated"),
        final.get("confidence"),
    )
    return ChatResponse(
        conversation_id=request.conversation_id or uuid4(),
        message_id=request.message_id,
        text=final.get("answer") or "",
        confidence=final.get("confidence", 0.0),
        escalated=final.get("escalated", False),
        sources=_to_sources(final.get("chunks") or []),
    )


def _initial_state(request: ChatRequest, installation_id: UUID) -> AgentState:
    return {
        "text": request.text,
        "image_base64": request.image_base64,
        "installation_id": str(installation_id),
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
