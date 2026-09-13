"""Схемы админского журнала операционных событий."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class LogEventType(StrEnum):
    """Тип события, которое админ видит в журнале."""

    ESCALATION = "escalation"
    CONVERSATION_RESOLVED = "conversation_resolved"
    DOCUMENT_INDEXED = "document_indexed"
    DOCUMENT_FAILED = "document_failed"


class LogEventOut(BaseModel):
    """Одна строка журнала для админки."""

    id: str
    occurred_at: datetime
    event_type: LogEventType
    conversation_id: UUID | None
    document_id: UUID | None
    message: str


class LogEventListOut(BaseModel):
    """Страница журнала, новые сверху."""

    items: list[LogEventOut]
    page: int
    page_size: int
    total: int


class LogListParams(BaseModel):
    """Фильтры списка — для селектора."""

    installation_id: UUID
    event_type: LogEventType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)
