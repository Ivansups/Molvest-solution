"""Сообщение в диалоге."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MessageRole, str_enum
from app.models.time import utc_now

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.escalation import Escalation


class Message(Base):
    """Реплика пользователя, ассистента или системы."""

    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "uq_messages_channel_message_id",
            "channel",
            "channel_message_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        str_enum(MessageRole),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Канал и внешний id события, из которого создано сообщение (для
    # идемпотентности вебхуков). У сообщений, порождённых агентом, — NULL.
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    channel_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sources: Mapped[list[object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    escalation: Mapped["Escalation | None"] = relationship(
        back_populates="message",
        uselist=False,
    )
