"""Схемы вебхука живого треда Bitrix."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


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


# ── Бот открытой линии: ONIMBOTMESSAGEADD (сценарий 1 ТЗ) ─────────────────
# Bitrix шлёт PHP-style form (`data[PARAMS][DIALOG_ID]`) или JSON. Ключи
# PARAMS часто в верхнем регистре; парсим либерально.


class BitrixBotParams(BaseModel):
    """data.PARAMS события бота: диалог, текст, автор."""

    DIALOG_ID: str | int | None = None
    MESSAGE: str | None = None
    MESSAGE_ID: str | int | None = None
    FROM_USER_ID: str | int | None = None
    TO_USER_ID: str | int | None = None
    AUTHOR_TYPE: str | None = None
    FILES: list[dict[str, object]] = []

    @model_validator(mode="before")
    @classmethod
    def _uppercase_keys(cls, data: object) -> object:
        return _uppercase_dict_keys(data)


class BitrixBotInfo(BaseModel):
    """data.BOT: идентификатор бота в событии."""

    BOT_ID: str | int | None = None
    ID: str | int | None = None

    @model_validator(mode="before")
    @classmethod
    def _uppercase_keys(cls, data: object) -> object:
        return _uppercase_dict_keys(data)


class BitrixBotData(BaseModel):
    """data события ONIMBOTMESSAGEADD."""

    PARAMS: BitrixBotParams | None = None
    BOT: BitrixBotInfo | None = None

    @model_validator(mode="before")
    @classmethod
    def _uppercase_keys(cls, data: object) -> object:
        return _uppercase_dict_keys(data)


class BitrixBotEvent(BaseModel):
    """Входящее событие бота открытой линии."""

    event: str | None = None
    data: BitrixBotData | None = None
    auth: BitrixOpenLinesAuth | None = None


class BitrixBotResponse(BaseModel):
    """Ответ вебхука бота: processed / duplicate / ignored."""

    conversation_id: UUID | None = None
    status: Literal["processed", "duplicate", "ignored"]
    reply: str | None = None
    escalated: bool = False
    delivered: bool = False


def php_form_to_mapping(form: dict[str, str]) -> dict[str, object]:
    """Разворачивает PHP-style ключи `a[b][c]` во вложенный dict."""
    root: dict[str, object] = {}
    for key, value in form.items():
        _assign_php_key(root, key, value)
    return root


def _uppercase_dict_keys(data: object) -> object:
    """Поднимает ключи dict в верхний регистр (PARAMS vs params)."""
    if not isinstance(data, dict):
        return data
    return {
        (str(key).upper() if isinstance(key, str) else key): value
        for key, value in data.items()
    }


def _assign_php_key(root: dict[str, object], key: str, value: str) -> None:
    parts = _php_key_parts(key)
    if not parts:
        return
    cursor: dict[str, object] = root
    for part in parts[:-1]:
        nested = cursor.get(part)
        if not isinstance(nested, dict):
            nested = {}
            cursor[part] = nested
        cursor = nested
    cursor[parts[-1]] = value


def _php_key_parts(key: str) -> list[str]:
    """`data[PARAMS][DIALOG_ID]` → `['data', 'PARAMS', 'DIALOG_ID']`."""
    parts: list[str] = []
    buf = ""
    index = 0
    while index < len(key):
        char = key[index]
        if char == "[":
            if buf:
                parts.append(buf)
                buf = ""
            close = key.find("]", index)
            if close < 0:
                buf += key[index:]
                break
            parts.append(key[index + 1 : close])
            index = close + 1
            continue
        buf += char
        index += 1
    if buf:
        parts.append(buf)
    return [part for part in parts if part]
