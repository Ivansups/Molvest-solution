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


# ── Реальный портал: события открытой линии (сценарий 1) ──────────────────
# Парсинг либеральный: контракт REST-коннектора ОЛ отличается по версиям
# портала, поэтому все интересующие поля опциональны, лишние ключи игнорируются
# (extra='ignore' по умолчанию в Pydantic). Обязательность проверяется в сервисе.


class BitrixOpenLinesAuth(BaseModel):
    """auth блока webhook: токен приложения и домен портала."""

    application_token: str | None = None
    domain: str | None = None


class BitrixOpenLinesAuthor(BaseModel):
    """Автор сообщения (data.message.author): id и тип."""

    id: str | int | None = None
    type: str | None = None


class BitrixOpenLinesMessage(BaseModel):
    """Сообщение из data.message события открытой линии."""

    id: str | int | None = None
    user_id: str | int | None = None
    text: str | None = None
    # Автор встречается в разных форматах: плоский user_id или объект author.
    author: BitrixOpenLinesAuthor | None = None
    # Картинки/файлы приходят разными наборами полей; для best-effort храним как есть.
    img: list[dict[str, object]] = []
    files: list[dict[str, object]] = []


class BitrixOpenLinesConnector(BaseModel):
    """data.connector: коннектор, линия и id диалога на стороне канала."""

    connector_id: str | None = None
    line_id: str | int | None = None
    chat_id: str | int | None = None


class BitrixOpenLinesData(BaseModel):
    """data события открытой линии."""

    connector: BitrixOpenLinesConnector | None = None
    message: BitrixOpenLinesMessage | None = None


class BitrixOpenLinesEvent(BaseModel):
    """Входящее событие открытой линии Bitrix24 (сценарий 1)."""

    data: BitrixOpenLinesData | None = None
    auth: BitrixOpenLinesAuth | None = None


class BitrixOpenLinesResponse(BaseModel):
    """Ответ вебхука открытой линии: маппинг и результат исходящей отправки."""

    conversation_id: UUID
    status: Literal["processed", "duplicate"]
    reply: str | None = None
    escalated: bool = False
    delivered: bool = False
