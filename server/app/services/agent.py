"""Запуск диалогового графа для одного сообщения чата с персистом диалога."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_graph
from app.agent.state import AgentState, HistoryTurn, RetrievedChunk
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.models.time import utc_now
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.selectors.conversations import list_recent_messages
from app.services.conversations import (
    GUEST_ESCALATION_TEXT,
    persist_guest_hold,
    persist_turn,
)
from app.services.runtime_settings import get_effective_operator_assist_mode

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 4
_IMAGE_HOLD_TEXT = "Пользователь отправил изображение"


class ConversationConflictError(Exception):
    """Диалог нельзя продолжить этим ходом (resolved или конфликт статуса)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


async def run_chat_turn(
    request: ChatRequest,
    session: AsyncSession,
) -> ChatResponse:
    """Прогоняет запрос через LangGraph, пишет диалог и мапит в контракт."""
    turn_started_at = utc_now()
    installation_id = workspace_to_installation_id(request.workspace_id)
    existing = await _load_conversation(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
    )
    if existing is not None and existing.status == ConversationStatus.RESOLVED:
        raise ConversationConflictError("Диалог уже закрыт")
    if (
        existing is not None
        and existing.status == ConversationStatus.ESCALATED
        and get_effective_operator_assist_mode() == "draft"
    ):
        await persist_guest_hold(
            session,
            conversation=existing,
            user_text=_hold_user_text(request),
            user_image=None,
            user_created_at=turn_started_at,
        )
        logger.info(
            "draft hold conversation_id=%s без графа",
            existing.id,
        )
        return ChatResponse(
            conversation_id=existing.id,
            message_id=request.message_id,
            text=GUEST_ESCALATION_TEXT,
            confidence=0.0,
            escalated=True,
            sources=[],
        )

    history = await _load_history(session, existing)
    logger.info(
        "граф старт message_id=%s installation_id=%s history=%s status=%s",
        request.message_id,
        installation_id,
        len(history),
        existing.status.value if existing is not None else "open",
    )
    await session.commit()
    final = await get_graph().ainvoke(_initial_state(request, installation_id, history))
    logger.info(
        "граф конец message_id=%s intent=%s escalated=%s confidence=%s",
        request.message_id,
        final.get("intent"),
        final.get("escalated"),
        final.get("confidence"),
    )

    existing = await _load_conversation(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
    )
    if existing is not None and existing.status == ConversationStatus.RESOLVED:
        raise ConversationConflictError("Диалог уже закрыт")

    sources = _to_sources(final.get("chunks") or [])
    escalated = bool(final.get("escalated", False))
    confidence = float(final.get("confidence", 0.0))
    answer = final.get("answer") or ""
    user_text = _user_content(request, final)
    if (
        existing is not None
        and existing.status == ConversationStatus.ESCALATED
        and escalated
    ):
        await persist_guest_hold(
            session,
            conversation=existing,
            user_text=user_text,
            user_image=None,
            user_created_at=turn_started_at,
        )
        return ChatResponse(
            conversation_id=existing.id,
            message_id=request.message_id,
            text=GUEST_ESCALATION_TEXT,
            confidence=confidence,
            escalated=True,
            sources=[],
        )

    text = GUEST_ESCALATION_TEXT if escalated else answer
    persist_sources = [] if escalated else sources

    persisted = await persist_turn(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
        user_id=request.user_id,
        user_text=user_text,
        user_image=None,
        assistant_content=text,
        confidence=confidence,
        escalated=escalated,
        sources=persist_sources,
        user_created_at=turn_started_at,
    )

    return ChatResponse(
        conversation_id=persisted.conversation.id,
        message_id=request.message_id,
        text=text,
        confidence=confidence,
        escalated=escalated,
        sources=persist_sources,
    )


def _hold_user_text(request: ChatRequest) -> str | None:
    """Текст гостя в draft-hold: без vision, картинка не пишется в image_url."""
    if request.text and request.text.strip():
        return request.text
    if request.image_base64:
        return _IMAGE_HOLD_TEXT
    return request.text


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


async def _load_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
) -> Conversation | None:
    if conversation_id is None:
        return None
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.installation_id != installation_id:
        return None
    return conversation


async def _load_history(
    session: AsyncSession,
    conversation: Conversation | None,
) -> list[HistoryTurn]:
    if conversation is None:
        return []
    rows = await list_recent_messages(session, conversation.id, limit=_HISTORY_LIMIT)
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
