"""Модель диалога с пользователем."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ConversationStatus, str_enum
from app.models.time import utc_now

if TYPE_CHECKING:
    from app.models.escalation import Escalation
    from app.models.message import Message


class Conversation(Base):
    """Диалог техподдержки. Статус меняется только через сервис перехода."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    installation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        str_enum(ConversationStatus),
        nullable=False,
        default=ConversationStatus.OPEN,
        index=True,
    )
    suggested_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
