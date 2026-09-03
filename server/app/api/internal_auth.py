"""Проверка внутреннего сервисного токена для admin API."""

from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_internal_service_token(
    authorization: Annotated[str | None, Header()] = None,
    x_internal_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Пускает только запросы Next-сервера с INTERNAL_SERVICE_TOKEN."""
    expected_token = settings.internal_service_token.strip()
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_SERVICE_TOKEN не настроен.",
        )

    bearer_matches = authorization is not None and compare_digest(
        authorization,
        f"Bearer {expected_token}",
    )
    header_matches = x_internal_service_token is not None and compare_digest(
        x_internal_service_token,
        expected_token,
    )
    if not bearer_matches and not header_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется внутренний сервисный токен.",
        )
