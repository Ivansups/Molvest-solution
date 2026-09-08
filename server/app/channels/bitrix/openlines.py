"""Вебхук входящих событий открытой линии реального портала Bitrix24.

Защищён токеном приложения (auth.application_token) и доменом портала, а не
внутренним токеном: событие приходит с серверов Bitrix, которые его не знают.
Fail-closed: пустой или несовпадающий секрет → 403.
"""

import logging
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status

from app.channels.bitrix.schemas import (
    BitrixOpenLinesEvent,
    BitrixOpenLinesResponse,
)
from app.core.config import settings
from app.db.session import SessionDep
from app.services.agent import ConversationConflictError
from app.services.openlines import process_openlines_event

router = APIRouter(prefix="/webhook", tags=["bitrix"])

logger = logging.getLogger(__name__)

_MISSING_CHAT_MSG = "Событие не содержит chat_id диалога открытой линии"


@router.post("/bitrix/openlines", response_model=BitrixOpenLinesResponse)
async def bitrix_openlines_webhook(
    event: BitrixOpenLinesEvent,
    session: SessionDep,
) -> BitrixOpenLinesResponse:
    """Принимает событие открытой линии и возвращает результат обработки."""
    _validate_auth(event)

    chat_id = _extract_chat_id(event)
    message_id = _extract_message_id(event)
    if chat_id is None or message_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_MISSING_CHAT_MSG,
        )

    try:
        return await process_openlines_event(session, event)
    except ConversationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from exc


def _validate_auth(event: BitrixOpenLinesEvent) -> None:
    """Проверяет токен приложения и домен портала (fail-closed, 403)."""
    expected_host = _portal_host()
    if not settings.bitrix_application_token or expected_host is None:
        raise _forbidden("Канал Bitrix24 не сконфигурирован")
    auth = event.auth
    if auth is None or not auth.application_token or not auth.domain:
        raise _forbidden("Отсутствует токен приложения")
    given = auth.application_token
    expected_token = settings.bitrix_application_token
    matches = secrets.compare_digest(given, expected_token)
    if len(given) != len(expected_token) or not matches:
        raise _forbidden("Неверный токен приложения")
    if auth.domain.strip().lower() != expected_host:
        logger.warning(
            "bitrix: домен события %s, ожидается %s",
            auth.domain,
            expected_host,
        )
        raise _forbidden("Домен портала не совпадает")


def _portal_host() -> str | None:
    """Хост из BITRIX_PORTAL_URL (нижний регистр) или None, если не задан."""
    if not settings.bitrix_portal_url:
        return None
    return urlparse(settings.bitrix_portal_url).netloc.lower()


def _extract_chat_id(event: BitrixOpenLinesEvent) -> str | None:
    """id диалога открытой линии из data.connector.chat_id."""
    connector = event.data.connector if event.data else None
    value = connector.chat_id if connector else None
    return None if value is None else str(value)


def _extract_message_id(event: BitrixOpenLinesEvent) -> str | None:
    """Внешний id сообщения из data.message.id."""
    message = event.data.message if event.data else None
    value = message.id if message else None
    return None if value is None else str(value)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
