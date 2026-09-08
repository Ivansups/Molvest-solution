"""Ответ оператора, закрытие тикета и черновик по кнопке."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.models.time import utc_now
from app.selectors.conversations import get_conversation
from app.services.agent import ConversationConflictError
from app.services.conversation_status import (
    IllegalStatusTransitionError,
    transition_status,
)
from app.services.draft import generate_draft

logger = logging.getLogger(__name__)


class ConversationNotFoundError(Exception):
    """Диалог не найден в этой установке."""


async def add_operator_reply(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    installation_id: UUID,
    text: str,
) -> Message:
    """Пишет сообщение оператора и очищает черновик. Граф не запускается."""
    conversation = await _require_conversation(
        session, conversation_id, installation_id
    )
    if conversation.status != ConversationStatus.ESCALATED:
        raise ConversationConflictError(
            "Ответ оператора только для эскалированного диалога"
        )
    message = Message(
        conversation=conversation,
        role=MessageRole.OPERATOR,
        content=text,
    )
    conversation.suggested_response = None
    session.add(message)
    await session.commit()
    await session.refresh(message)
    logger.info(
        "ответ оператора conversation_id=%s message_id=%s",
        conversation.id,
        message.id,
    )
    return message


async def resolve_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    installation_id: UUID,
) -> Conversation:
    """escalated → resolved, идемпотентно на уже resolved."""
    conversation = await _require_conversation(
        session, conversation_id, installation_id
    )
    if conversation.status == ConversationStatus.RESOLVED:
        logger.info("resolve повтор conversation_id=%s", conversation.id)
        return conversation
    try:
        transition_status(conversation, ConversationStatus.RESOLVED)
    except IllegalStatusTransitionError as exc:
        raise ConversationConflictError(str(exc)) from exc
    now = utc_now()
    for escalation in conversation.escalations:
        if escalation.resolved_at is None:
            escalation.resolved_at = now
    conversation.suggested_response = None
    await session.commit()
    await session.refresh(conversation)
    logger.info("тикет закрыт conversation_id=%s", conversation.id)
    return conversation


async def generate_suggestion(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    installation_id: UUID,
) -> Conversation:
    """Retrieve + generate в черновик. Ленту и статус не трогает."""
    conversation = await _require_conversation(
        session, conversation_id, installation_id
    )
    if conversation.status != ConversationStatus.ESCALATED:
        raise ConversationConflictError("Черновик только для эскалированного диалога")
    last_user = _last_user_message(conversation)
    if last_user is None:
        raise ConversationConflictError("Нет сообщения гостя для черновика")
    answer = await generate_draft(
        session, conversation=conversation, query=last_user.content
    )

    conversation = await _require_conversation(
        session, conversation_id, installation_id
    )
    if conversation.status != ConversationStatus.ESCALATED:
        raise ConversationConflictError("Черновик только для эскалированного диалога")
    conversation.suggested_response = answer
    await session.commit()
    logger.info("черновик обновлён conversation_id=%s", conversation.id)
    return conversation


async def _require_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    installation_id: UUID,
) -> Conversation:
    conversation = await get_conversation(session, conversation_id, installation_id)
    if conversation is None:
        raise ConversationNotFoundError
    return conversation


def _last_user_message(conversation: Conversation) -> Message | None:
    users = [m for m in conversation.messages if m.role == MessageRole.USER]
    if not users:
        return None
    return max(users, key=lambda m: m.created_at)
