"""Запуск диалогового графа для одного сообщения чата с персистом диалога."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_graph
from app.agent.state import AgentState, HistoryTurn, RetrievedChunk
from app.models.conversation import Conversation
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.selectors.conversations import list_recent_messages
from app.services.conversations import GUEST_ESCALATION_TEXT, persist_turn

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 4


async def run_chat_turn(
    request: ChatRequest,
    session: AsyncSession,
) -> ChatResponse:
    """Прогоняет запрос через LangGraph, пишет диалог и мапит в контракт."""
    installation_id = workspace_to_installation_id(request.workspace_id)
    history = await _load_history(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
    )
    logger.info(
        "граф старт message_id=%s installation_id=%s history=%s",
        request.message_id,
        installation_id,
        len(history),
    )
    final = await get_graph().ainvoke(_initial_state(request, installation_id, history))
    logger.info(
        "граф конец message_id=%s intent=%s escalated=%s confidence=%s",
        request.message_id,
        final.get("intent"),
        final.get("escalated"),
        final.get("confidence"),
    )

    sources = _to_sources(final.get("chunks") or [])
    escalated = bool(final.get("escalated", False))
    confidence = float(final.get("confidence", 0.0))
    answer = final.get("answer") or ""
    text = GUEST_ESCALATION_TEXT if escalated else answer

    persisted = await persist_turn(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
        user_id=request.user_id,
        user_text=_user_content(request, final),
        user_image=None,
        assistant_content=text,
        confidence=confidence,
        escalated=escalated,
        sources=sources,
    )

    return ChatResponse(
        conversation_id=persisted.conversation.id,
        message_id=request.message_id,
        text=text,
        confidence=confidence,
        escalated=escalated,
        sources=sources,
    )


def _user_content(request: ChatRequest, final: dict[str, object]) -> str | None:
    """Реплика пользователя для БД — `query`, а не сырой текст.

    `query` после vision содержит описание скриншота, а сам скриншот не
    сохраняется: `Message.image_url` рассчитан на ссылку, а не на base64.
    Без описания у сообщения с одной картинкой не осталось бы содержимого.
    """
    query = final.get("query")
    if isinstance(query, str) and query:
        return query
    return request.text


async def _load_history(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
) -> list[HistoryTurn]:
    if conversation_id is None:
        return []
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.installation_id != installation_id:
        return []
    rows = await list_recent_messages(session, conversation_id, limit=_HISTORY_LIMIT)
    return [HistoryTurn(role=row.role.value, content=row.content) for row in rows]


def _initial_state(
    request: ChatRequest,
    installation_id: UUID,
    history: list[HistoryTurn],
) -> AgentState:
    return {
        "text": request.text,
        "image_base64": request.image_base64,
        "installation_id": str(installation_id),
        "query": "",
        "intent": "empty",
        "history": history,
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
