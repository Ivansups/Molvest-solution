"""Запись хода чата: диалог, сообщения и эскалация.

Весь persist `POST /chat` живёт здесь, а не в узлах графа: граф остаётся
чистым от БД и говорит только `escalated`/`confidence`/`answer`.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.models.time import utc_now
from app.schemas.chat import Source
from app.services.conversation_status import transition_status

logger = logging.getLogger(__name__)

# Каноническая фраза для гостя при эскалации на оператора техподдержки.
GUEST_ESCALATION_TEXT = "Вопрос передан оператору техподдержки."
# Текст в ленте, когда гость прислал только картинку (без vision-описания).
IMAGE_HOLD_TEXT = "Пользователь отправил изображение"

_ESCALATED_TO = "operator"


@dataclass
class PersistedTurn:
    """Результат записи одного хода: диалог и сообщение ассистента."""

    conversation: Conversation
    assistant_message: Message


async def find_or_create_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
    user_id: str,
) -> Conversation:
    """Возвращает существующий диалог или создаёт новый со статусом open.

    Диалог с чужим `installation_id` игнорируется и трактуется как
    отсутствующий, чтобы клиент одной установки не мог дописывать сообщения
    или эскалировать диалог другой установки, подставив чужой id.
    """
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None and conversation.installation_id == installation_id:
            return conversation
    conversation = Conversation(
        installation_id=installation_id,
        user_id=user_id,
        status=ConversationStatus.OPEN,
    )
    session.add(conversation)
    return conversation


def add_user_message(
    conversation: Conversation,
    *,
    text: str | None,
    image_base64: str | None,
    created_at: datetime | None = None,
    channel: str | None = None,
    channel_message_id: str | None = None,
) -> Message:
    """Сообщение пользователя в диалоге (в памяти, без flush)."""
    message = Message(
        conversation=conversation,
        role=MessageRole.USER,
        content=text or "",
        image_url=image_base64,
        channel=channel,
        channel_message_id=channel_message_id,
    )
    # Метка начала хода: иначе user и assistant пишутся с одним utc_now
    # в конце и среднее время ответа всегда ~0.
    if created_at is not None:
        message.created_at = created_at
    return message


def add_assistant_message(
    conversation: Conversation,
    *,
    content: str,
    confidence: float,
    escalated: bool,
    sources: list[Source],
    created_at: datetime | None = None,
) -> Message:
    """Сообщение ассистента: реальный ответ или гостевой текст эскалации."""
    role = MessageRole.SYSTEM if escalated else MessageRole.ASSISTANT
    message = Message(
        conversation=conversation,
        role=role,
        content=content,
        confidence=confidence,
        escalated=escalated,
        sources=[source.model_dump(mode="json") for source in sources],
    )
    if created_at is not None:
        message.created_at = created_at
    return message


def escalate_conversation(
    session: AsyncSession,
    conversation: Conversation,
    *,
    assistant_message: Message,
    reason: str,
) -> None:
    """Переводит open → escalated через сервис и создаёт строку Escalation.

    Идемпотентно: если диалог уже escalated, вторую строку не создаём и
    статус не меняем. Вызов до flush, чтобы у message был id.
    """
    if conversation.status == ConversationStatus.OPEN:
        transition_status(conversation, ConversationStatus.ESCALATED)
        escalation = Escalation(
            conversation=conversation,
            message=assistant_message,
            reason=reason,
            escalated_to=_ESCALATED_TO,
        )
        session.add(escalation)


async def persist_guest_hold(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_text: str | None,
    user_image: str | None,
    user_created_at: datetime | None = None,
    channel: str | None = None,
    channel_message_id: str | None = None,
) -> Conversation:
    """Пишет только реплику гостя в уже эскалированный диалог, без LLM."""
    session.add(
        add_user_message(
            conversation,
            text=user_text,
            image_base64=user_image,
            created_at=user_created_at,
            channel=channel,
            channel_message_id=channel_message_id,
        )
    )
    await session.commit()
    logger.info(
        "ход гостя в эскалации conversation_id=%s без ответа модели",
        conversation.id,
    )
    return conversation


async def persist_turn(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
    user_id: str,
    user_text: str | None,
    user_image: str | None,
    assistant_content: str,
    confidence: float,
    escalated: bool,
    sources: list[Source],
    escalation_reason: str | None = None,
    user_created_at: datetime | None = None,
    channel: str | None = None,
    channel_message_id: str | None = None,
) -> PersistedTurn:
    """Записывает один ход в одной транзакции и коммитит."""
    conversation = await find_or_create_conversation(
        session,
        conversation_id=conversation_id,
        installation_id=installation_id,
        user_id=user_id,
    )
    session.add(
        add_user_message(
            conversation,
            text=user_text,
            image_base64=user_image,
            created_at=user_created_at,
            channel=channel,
            channel_message_id=channel_message_id,
        )
    )
    assistant = add_assistant_message(
        conversation,
        content=assistant_content,
        confidence=confidence,
        escalated=escalated,
        sources=sources,
        created_at=utc_now(),
    )
    session.add(assistant)
    if escalated:
        reason = escalation_reason or f"Низкая уверенность ретривала: {confidence:.2f}"
        escalate_conversation(
            session,
            conversation,
            assistant_message=assistant,
            reason=reason,
        )
    await session.commit()
    logger.info(
        "ход записан conversation_id=%s escalated=%s",
        conversation.id,
        escalated,
    )
    return PersistedTurn(conversation=conversation, assistant_message=assistant)
