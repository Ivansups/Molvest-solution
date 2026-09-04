"""Схемы ответов и фильтров для API диалогов этапа 6."""

from datetime import datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message


class MessageOut(BaseModel):
    """Сообщение диалога."""

    id: UUID
    role: MessageRole
    content: str
    confidence: float | None
    escalated: bool
    sources: list[dict[str, object]]
    created_at: datetime


class EscalationOut(BaseModel):
    """Запись о передаче оператору."""

    id: UUID
    message_id: UUID
    reason: str
    escalated_to: str
    resolved_at: datetime | None


class ConversationOut(BaseModel):
    """Диалог в списке — без сообщений."""

    id: UUID
    installation_id: UUID
    user_id: str
    status: ConversationStatus
    created_at: datetime
    suggested_response: str | None = None


class ConversationDetailOut(ConversationOut):
    """Диалог вместе с сообщениями и эскалациями."""

    messages: list[MessageOut]
    escalations: list[EscalationOut]


class ConversationListOut(BaseModel):
    """Страница списка диалогов."""

    items: list[ConversationOut]
    page: int
    page_size: int
    total: int


class OperatorMessageIn(BaseModel):
    """Ответ оператора в эскалированный диалог."""

    installation_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class OperatorActionIn(BaseModel):
    """Resolve или suggest: достаточно installation_id."""

    installation_id: UUID


class ConversationListParams(BaseModel):
    """Параметры списка — для селектора."""

    installation_id: UUID
    user_id: str | None = None
    status: ConversationStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


def conversation_to_out(conversation: Conversation) -> ConversationOut:
    """Собирает ответ API из модели."""
    return ConversationOut(
        id=conversation.id,
        installation_id=conversation.installation_id,
        user_id=conversation.user_id,
        status=conversation.status,
        created_at=conversation.created_at,
        suggested_response=conversation.suggested_response,
    )


def message_to_out(message: Message) -> MessageOut:
    """Сообщение в виде ответа API."""
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        confidence=message.confidence,
        escalated=message.escalated,
        sources=cast("list[dict[str, object]]", message.sources or []),
        created_at=message.created_at,
    )


def escalation_to_out(escalation: Escalation) -> EscalationOut:
    """Эскалацию в виде ответа API."""
    return EscalationOut(
        id=escalation.id,
        message_id=escalation.message_id,
        reason=escalation.reason,
        escalated_to=escalation.escalated_to,
        resolved_at=escalation.resolved_at,
    )


def conversation_to_detail(
    conversation: Conversation,
    messages: list[Message],
    escalations: list[Escalation],
) -> ConversationDetailOut:
    """Диалог с сообщениями и эскалациями."""
    return ConversationDetailOut(
        **conversation_to_out(conversation).model_dump(),
        messages=[
            message_to_out(m) for m in sorted(messages, key=lambda row: row.created_at)
        ],
        escalations=[
            escalation_to_out(e) for e in sorted(escalations, key=lambda row: row.id)
        ],
    )


class ConversationMetrics(BaseModel):
    """Агрегированные метрики этапа 6."""

    auto_answer_percent: float
    avg_response_time_seconds: float
    escalation_count: int
