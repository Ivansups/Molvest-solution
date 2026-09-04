"""Проверка служебного токена Next.js → FastAPI."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: Annotated[str | None, Header(alias=INTERNAL_TOKEN_HEADER)] = None,
) -> None:
    """401, если токен задан в конфиге и заголовок не совпал. Пустой — пропуск."""
    expected = settings.internal_service_token
    if not expected:
        return
    given = x_internal_token or ""
    if len(given) != len(expected) or not hmac.compare_digest(given, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный служебный токен",
        )
