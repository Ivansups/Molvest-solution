"""Обработка событий живого Bitrix-треда: маппинг, идемпотентность, draft/auto."""

import logging
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.schemas import (
    BitrixWebhookEvent,
    BitrixWebhookResponse,
)
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest
from app.services.agent import ConversationConflictError, run_chat_turn
from app.services.conversations import add_user_message
from app.services.draft import generate_draft
from app.services.runtime_settings import get_effective_operator_assist_mode

logger = logging.getLogger(__name__)

_CHANNEL = "bitrix"
# Детерминированный message_id для ChatRequest из строкового id события.
_CHAT_MSG_NS = UUID("41f7c1f7-0000-4f6e-9c6e-0000000000a1")
_DEFAULT_USER = "bitrix"


async def process_live_thread_event(
    session: AsyncSession,
    event: BitrixWebhookEvent,
) -> BitrixWebhookResponse:
    """Обрабатывает одно сообщение треда: дубли, operator, draft, auto."""
    existing = await _find_by_channel_message(session, event.message_id)
    if existing is not None:
        logger.info("дубль %s message_id=%s", _CHANNEL, event.message_id)
        return BitrixWebhookResponse(
            conversation_id=existing.conversation_id,
            status="duplicate",
        )

    installation_id = workspace_to_installation_id(event.workspace_id)

    if event.sender == "operator":
        return await _process_operator(session, event, installation_id)

    if get_effective_operator_assist_mode() == "draft":
        return await _process_draft(session, event, installation_id)

    return await _process_auto(session, event, installation_id)


# ── Operator ────────────────────────────────────────────────────────────


async def _process_operator(
    session: AsyncSession,
    event: BitrixWebhookEvent,
    installation_id: UUID,
) -> BitrixWebhookResponse:
    """Пассивная запись сообщения оператора: граф не запускается."""
    conversation = await _get_or_create_thread(
        session,
        installation_id=installation_id,
        thread_id=event.thread_id,
        user_id=event.user_id or _DEFAULT_USER,
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
    logger.info(
        "сообщение оператора conversation_id=%s message_id=%s",
        conversation.id,
        event.message_id,
    )
    return BitrixWebhookResponse(
        conversation_id=conversation.id,
        status="processed",
    )


# ── Draft ───────────────────────────────────────────────────────────────


async def _process_draft(
    session: AsyncSession,
    event: BitrixWebhookEvent,
    installation_id: UUID,
) -> BitrixWebhookResponse:
    """Черновик оператору: retrieve + generate, ответ пользователю не уходит."""
    conversation = await _get_or_create_thread(
        session,
        installation_id=installation_id,
        thread_id=event.thread_id,
        user_id=event.user_id or _DEFAULT_USER,
    )
    session.add(
        add_user_message(
            conversation,
            text=event.text,
            image_base64=None,
            channel=_CHANNEL,
            channel_message_id=event.message_id,
        )
    )
    await session.commit()

    draft = None
    if event.text and event.text.strip():
        draft = await generate_draft(
            session, conversation=conversation, query=event.text
        )
        conversation.suggested_response = draft
        await session.commit()

    logger.info(
        "черновик треда conversation_id=%s message_id=%s",
        conversation.id,
        event.message_id,
    )
    return BitrixWebhookResponse(
        conversation_id=conversation.id,
        status="processed",
        draft=draft,
    )


# ── Auto ────────────────────────────────────────────────────────────────


async def _process_auto(
    session: AsyncSession,
    event: BitrixWebhookEvent,
    installation_id: UUID,
) -> BitrixWebhookResponse:
    """Полный граф: ответ пользователю при высоком confidence, иначе эскалация."""
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        thread_id=event.thread_id,
    )

    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None or conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        conversation_id: UUID | None = conversation.id
    else:
        conversation_id = None

    request = ChatRequest(
        message_id=uuid5(_CHAT_MSG_NS, event.message_id),
        workspace_id=event.workspace_id,
        conversation_id=conversation_id,
        text=event.text,
        image_base64=None,
        user_id=event.user_id or _DEFAULT_USER,
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
                thread_id=event.thread_id,
                installation_id=installation_id,
                conversation_id=response.conversation_id,
            )
        )
        await session.commit()

    logger.info(
        "auto обработано conversation_id=%s escalated=%s message_id=%s",
        response.conversation_id,
        response.escalated,
        event.message_id,
    )
    return BitrixWebhookResponse(
        conversation_id=response.conversation_id,
        status="processed",
        reply=None if response.escalated else response.text,
        escalated=response.escalated,
    )


# ── Helpers ─────────────────────────────────────────────────────────────


async def _find_by_channel_message(
    session: AsyncSession,
    message_id: str,
) -> Message | None:
    """Ранняя проверка идемпотентности: дубль — без графа и персиста."""
    stmt = select(Message).where(
        Message.channel == _CHANNEL,
        Message.channel_message_id == message_id,
    )
    return (await session.scalars(stmt)).first()


async def _find_mapping(
    session: AsyncSession,
    *,
    installation_id: UUID,
    thread_id: str,
) -> ChannelThread | None:
    stmt = select(ChannelThread).where(
        ChannelThread.channel == _CHANNEL,
        ChannelThread.thread_id == thread_id,
        ChannelThread.installation_id == installation_id,
    )
    return (await session.scalars(stmt)).first()


async def _get_or_create_thread(
    session: AsyncSession,
    *,
    installation_id: UUID,
    thread_id: str,
    user_id: str,
) -> Conversation:
    """Возвращает диалог треда; создаёт диалог + маппинг при первом событии."""
    mapping = await _find_mapping(
        session, installation_id=installation_id, thread_id=thread_id
    )
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None:
            conversation = Conversation(
                installation_id=installation_id,
                user_id=user_id,
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
        user_id=user_id,
        status=ConversationStatus.OPEN,
    )
    session.add(conversation)
    await session.flush()
    session.add(
        ChannelThread(
            channel=_CHANNEL,
            thread_id=thread_id,
            installation_id=installation_id,
            conversation_id=conversation.id,
        )
    )
    return conversation
