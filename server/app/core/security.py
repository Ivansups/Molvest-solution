"""Проверка служебного токена Next.js → FastAPI."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def assert_internal_token(
    given: str | None,
    *,
    status_code: int = status.HTTP_401_UNAUTHORIZED,
) -> None:
    """Пустой конфиг — пропуск. Несовпадение — HTTPException с заданным кодом."""
    expected = settings.internal_service_token
    if not expected:
        return
    token = given or ""
    if len(token) != len(expected) or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status_code,
            detail="Неверный служебный токен",
        )


async def require_internal_token(
    x_internal_token: Annotated[str | None, Header(alias=INTERNAL_TOKEN_HEADER)] = None,
) -> None:
    """401, если токен задан в конфиге и заголовок не совпал. Пустой — пропуск."""
    assert_internal_token(x_internal_token)
