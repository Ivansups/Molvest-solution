"""Обработка тикета Redmine: маппинг, дубль, граф, handoff."""

import logging
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.redmine.rest import RedmineRestError, build_redmine_client
from app.channels.redmine.schemas import RedmineEvent, RedmineResponse
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest
from app.services.agent import ConversationConflictError, run_chat_turn
from app.services.channel_handoff import (
    fill_escalation_draft,
    persist_draft_followup,
    should_draft_followup,
)

logger = logging.getLogger(__name__)

_CHANNEL = "redmine"
_CHAT_MSG_NS = UUID("41f7c1f7-0000-4f6e-9c6e-0000000000c1")
_DEFAULT_USER = "redmine"


async def process_redmine_event(
    session: AsyncSession,
    event: RedmineEvent,
) -> RedmineResponse:
    """Дубль, оператор или гость тикета."""
    existing = await _find_by_channel_message(session, event.message_id)
    if existing is not None:
        logger.info("дубль %s message_id=%s", _CHANNEL, event.message_id)
        return RedmineResponse(
            conversation_id=existing.conversation_id,
            status="duplicate",
        )
    installation_id = workspace_to_installation_id(event.workspace_id)
    if event.sender == "operator":
        return await _process_operator(session, event, installation_id)
    return await _process_guest(session, event, installation_id)


async def _process_guest(
    session: AsyncSession,
    event: RedmineEvent,
    installation_id: UUID,
) -> RedmineResponse:
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        ticket_id=event.ticket_id,
    )
    conversation: Conversation | None = None
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None or conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        if await should_draft_followup(session, conversation):
            await persist_draft_followup(
                session,
                conversation=conversation,
                user_text=event.text,
                user_image=event.image_base64,
                channel=_CHANNEL,
                channel_message_id=event.message_id,
            )
            logger.info("redmine draft follow-up conversation_id=%s", conversation.id)
            return RedmineResponse(
                conversation_id=conversation.id,
                status="processed",
                escalated=conversation.status == ConversationStatus.ESCALATED,
            )

    request = ChatRequest(
        message_id=uuid5(_CHAT_MSG_NS, event.message_id),
        workspace_id=event.workspace_id,
        conversation_id=None if conversation is None else conversation.id,
        text=event.text,
        image_base64=event.image_base64,
        user_id=_DEFAULT_USER,
    )
    response = await run_chat_turn(
        request,
        session,
        channel=_CHANNEL,
        channel_message_id=event.message_id,
    )
    if mapping is None:
        session.add(
            ChannelThread(
                channel=_CHANNEL,
                thread_id=event.ticket_id,
                installation_id=installation_id,
                conversation_id=response.conversation_id,
            )
        )
        await session.commit()

    if response.escalated:
        await fill_escalation_draft(
            session,
            conversation_id=response.conversation_id,
            query=event.text,
        )
        return RedmineResponse(
            conversation_id=response.conversation_id,
            status="processed",
            escalated=True,
        )

    delivered = False
    if response.text:
        delivered = await _send_note(event.ticket_id, response.text)
    return RedmineResponse(
        conversation_id=response.conversation_id,
        status="processed",
        reply=response.text,
        delivered=delivered,
    )


async def _send_note(ticket_id: str, text: str) -> bool:
    client = build_redmine_client()
    if client is None:
        logger.warning("redmine исходящее не настроено")
        return False
    try:
        await client.add_note(ticket_id, text)
        return True
    except (RedmineRestError, OSError) as exc:
        logger.warning("redmine заметка не доставлена ticket_id=%s: %s", ticket_id, exc)
        return False
    finally:
        await client.aclose()


async def _process_operator(
    session: AsyncSession,
    event: RedmineEvent,
    installation_id: UUID,
) -> RedmineResponse:
    conversation = await _get_or_create_thread(
        session,
        installation_id=installation_id,
        ticket_id=event.ticket_id,
    )
    session.add(
        Message(
            conversation=conversation,
            role=MessageRole.OPERATOR,
            content=event.text or "",
            channel=_CHANNEL,
            channel_message_id=event.message_id,
        )
    )
    await session.commit()
    return RedmineResponse(
        conversation_id=conversation.id,
        status="processed",
    )


async def _find_by_channel_message(
    session: AsyncSession,
    message_id: str,
) -> Message | None:
    stmt = select(Message).where(
        Message.channel == _CHANNEL,
        Message.channel_message_id == message_id,
    )
    return (await session.scalars(stmt)).first()


async def _find_mapping(
    session: AsyncSession,
    *,
    installation_id: UUID,
    ticket_id: str,
) -> ChannelThread | None:
    stmt = select(ChannelThread).where(
        ChannelThread.channel == _CHANNEL,
        ChannelThread.thread_id == ticket_id,
        ChannelThread.installation_id == installation_id,
    )
    return (await session.scalars(stmt)).first()


async def _get_or_create_thread(
    session: AsyncSession,
    *,
    installation_id: UUID,
    ticket_id: str,
) -> Conversation:
    mapping = await _find_mapping(
        session, installation_id=installation_id, ticket_id=ticket_id
    )
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None:
            conversation = Conversation(
                installation_id=installation_id,
                user_id=_DEFAULT_USER,
                status=ConversationStatus.OPEN,
            )
            session.add(conversation)
            await session.flush()
            mapping.conversation_id = conversation.id
            return conversation
        if conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        return conversation
    conversation = Conversation(
        installation_id=installation_id,
        user_id=_DEFAULT_USER,
        status=ConversationStatus.OPEN,
    )
    session.add(conversation)
    await session.flush()
    session.add(
        ChannelThread(
            channel=_CHANNEL,
            thread_id=ticket_id,
            installation_id=installation_id,
            conversation_id=conversation.id,
        )
    )
    return conversation
