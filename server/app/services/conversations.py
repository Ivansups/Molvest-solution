"""Запись хода чата: диалог, сообщения и эскалация.

Весь persist `POST /chat` живёт здесь, а не в узлах графа: граф остаётся
чистым от БД и говорит только `escalated`/`confidence`/`answer`.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.schemas.chat import Source
from app.services.conversation_status import transition_status

logger = logging.getLogger(__name__)

# Каноническая фраза для гостя при эскалации на оператора техподдержки.
GUEST_ESCALATION_TEXT = "Вопрос передан оператору техподдержки."

_ESCALATED_TO = "operator"


class PersistedTurn:
    """Результат записи одного хода: диалог и сообщение ассистента."""

    def __init__(
        self,
        conversation: Conversation,
        assistant_message: Message,
    ) -> None:
        self.conversation = conversation
        self.assistant_message = assistant_message


async def find_or_create_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
    user_id: str,
) -> Conversation:
    """Возвращает существующий диалог или создаёт новый со статусом open."""
    if conversation_id is not None:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
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
) -> Message:
    """Сообщение пользователя в диалоге (в памяти, без flush)."""
    return Message(
        conversation=conversation,
        role=MessageRole.USER,
        content=text or "",
        image_url=image_base64,
    )


def add_assistant_message(
    conversation: Conversation,
    *,
    content: str,
    confidence: float,
    escalated: bool,
    sources: list[Source],
) -> Message:
    """Сообщение ассистента: реальный ответ или гостевой текст эскалации."""
    role = MessageRole.SYSTEM if escalated else MessageRole.ASSISTANT
    return Message(
        conversation=conversation,
        role=role,
        content=content,
        confidence=confidence,
        escalated=escalated,
        sources=[source.model_dump() for source in sources],
    )


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
) -> PersistedTurn:
    """Записывает один ход в одной транзакции и коммитит."""
    conversation = await find_or_create_conversation(
        session,
        conversation_id=conversation_id,
        installation_id=installation_id,
        user_id=user_id,
    )
    session.add(add_user_message(conversation, text=user_text, image_base64=user_image))
    assistant = add_assistant_message(
        conversation,
        content=assistant_content,
        confidence=confidence,
        escalated=escalated,
        sources=sources,
    )
    session.add(assistant)
    if escalated:
        reason = f"Низкая уверенность ретривала: {confidence:.2f}"
        escalate_conversation(
            session,
            conversation,
            assistant_message=assistant,
            reason=reason,
        )
    await session.commit()
    await session.refresh(conversation)
    await session.refresh(assistant)
    logger.info(
        "ход записан conversation_id=%s escalated=%s",
        conversation.id,
        escalated,
    )
    return PersistedTurn(conversation=conversation, assistant_message=assistant)
