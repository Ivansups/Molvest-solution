"""Схемы входящего события Redmine HelpDesk."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RedmineEvent(BaseModel):
    """Тикет: номер, id сообщения, автор, текст."""

    ticket_id: str = Field(pattern=r"^\d+$")
    message_id: str
    sender: Literal["user", "operator"]
    text: str | None = None
    image_base64: str | None = None
    workspace_id: str = "redmine"


class RedmineResponse(BaseModel):
    """Результат обработки тикета."""

    conversation_id: UUID
    status: Literal["processed", "duplicate"]
    reply: str | None = None
    escalated: bool = False
    delivered: bool = False
