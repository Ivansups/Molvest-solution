"""Контракт запроса/ответа для POST /chat (см. docs/ROADMAP.md, этап 1)."""

from uuid import UUID

from pydantic import BaseModel


class Source(BaseModel):
    """Источник ответа — документ базы знаний."""

    document_id: UUID
    title: str
    chunk_text: str


class ChatRequest(BaseModel):
    """Входящее сообщение пользователя."""

    message_id: UUID
    workspace_id: str
    conversation_id: UUID | None = None
    text: str | None = None
    image_base64: str | None = None
    user_id: str


class ChatResponse(BaseModel):
    """Ответ агента на сообщение пользователя."""

    conversation_id: UUID
    message_id: UUID
    text: str
    confidence: float
    escalated: bool
    sources: list[Source] = []
