"""Схемы вебхука живого треда Bitrix."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class BitrixWebhookEvent(BaseModel):
    """Входящее сообщение из открытого треда поддержки."""

    workspace_id: str
    thread_id: str
    message_id: str
    sender: Literal["user", "operator"]
    text: str | None = None
    user_id: str | None = None


class BitrixWebhookResponse(BaseModel):
    """Результат обработки: маппинг, черновик или ответ пользователю."""

    conversation_id: UUID
    status: Literal["processed", "duplicate"]
    draft: str | None = None
    reply: str | None = None
    escalated: bool = False
