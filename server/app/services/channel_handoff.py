"""Черновик оператору после канальной эскалации и follow-up в draft.

Виджетный POST /chat не вызывает эти функции: там первая эскалация
по-прежнему без generate (operator-assist).
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.services.conversations import IMAGE_HOLD_TEXT, persist_guest_hold
from app.services.draft import generate_draft
from app.services.runtime_settings import get_effective_operator_assist_mode

logger = logging.getLogger(__name__)


async def fill_escalation_draft(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    query: str | None,
) -> str | None:
    """После commit эскалации считает черновик и пишет suggested_response.

    Ошибка generate не откатывает статус: эскалация уже зафиксирована.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    text = (query or "").strip() or IMAGE_HOLD_TEXT
    return await _save_draft(
        session,
        conversation,
        text,
        warning="черновик эскалации не посчитан conversation_id=%s: %s",
    )


async def persist_draft_followup(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_text: str | None,
    user_image: str | None,
    channel: str,
    channel_message_id: str,
) -> str | None:
    """Реплика гостя в draft после оператора: лента + черновик, без автоответа."""
    await persist_guest_hold(
        session,
        conversation=conversation,
        user_text=user_text,
        user_image=user_image,
        channel=channel,
        channel_message_id=channel_message_id,
    )
    text = (user_text or "").strip()
    if not text:
        if user_image:
            text = IMAGE_HOLD_TEXT
        else:
            return None
    return await _save_draft(
        session,
        conversation,
        text,
        warning="черновик follow-up не посчитан conversation_id=%s: %s",
    )


async def should_draft_followup(
    session: AsyncSession,
    conversation: Conversation,
) -> bool:
    """True, если гость уже у оператора и режим draft — не автоответ."""
    if get_effective_operator_assist_mode() != "draft":
        return False
    if conversation.status == ConversationStatus.ESCALATED:
        return True
    stmt = (
        select(Message.id)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == MessageRole.OPERATOR,
        )
        .limit(1)
    )
    return (await session.scalars(stmt)).first() is not None


async def _save_draft(
    session: AsyncSession,
    conversation: Conversation,
    query: str,
    *,
    warning: str,
) -> str | None:
    try:
        draft = await generate_draft(session, conversation=conversation, query=query)
    except Exception as exc:
        logger.warning(warning, conversation.id, exc)
        return None
    conversation.suggested_response = draft
    await session.commit()
    return draft
