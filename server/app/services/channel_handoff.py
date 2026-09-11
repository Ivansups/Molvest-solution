"""Черновик оператору после канальной эскалации и follow-up в draft/agent.

Виджет в draft первую эскалацию не заполняет; в agent — вызывает
fill_escalation_draft после commit, если черновик ещё пуст.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.services.conversations import (
    GUEST_ESCALATION_TEXT,
    IMAGE_HOLD_TEXT,
    add_assistant_message,
    escalate_conversation,
    persist_guest_hold,
)
from app.services.draft import generate_draft
from app.services.runtime_settings import get_effective_operator_assist_mode

# OPEN + agent: оператор уже в треде, тикет должен попасть в очередь поддержки.
AGENT_OPEN_OPERATOR_REASON = "Режим agent: оператор ответил до эскалации"

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
    if conversation.suggested_response:
        logger.info(
            "черновик уже есть, generate не вызываем conversation_id=%s",
            conversation.id,
        )
        return conversation.suggested_response
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
    channel: str | None = None,
    channel_message_id: str | None = None,
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
    await escalate_if_agent_still_open(session, conversation)
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
    """True, если гость уже у оператора и режим draft/agent — не автоответ."""
    if get_effective_operator_assist_mode() not in ("draft", "agent"):
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


async def escalate_if_agent_still_open(
    session: AsyncSession,
    conversation: Conversation,
) -> None:
    """В agent эскалирует OPEN-тикет, если оператор уже писал в ленту.

    Иначе follow-up минует граф и тикет не попадает в очередь поддержки.
    Черновик и исходящие гостю не меняем — только статус и Escalation.
    """
    if get_effective_operator_assist_mode() != "agent":
        return
    if conversation.status != ConversationStatus.OPEN:
        return
    system = add_assistant_message(
        conversation,
        content=GUEST_ESCALATION_TEXT,
        confidence=0.0,
        escalated=True,
        sources=[],
    )
    session.add(system)
    await escalate_conversation(
        session,
        conversation,
        assistant_message=system,
        reason=AGENT_OPEN_OPERATOR_REASON,
    )
    await session.commit()


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
