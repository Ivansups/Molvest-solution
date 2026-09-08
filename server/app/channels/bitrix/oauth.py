"""OAuth-токены Bitrix24: установка приложения, обновление access_token.

`imconnector.*`/`imbot.*` требуют контекст установленного приложения — сам
статический `bitrix_app_token` для них не проходит (см.
openspec/changes/bitrix24-channel/design.md, D8). Секреты (client_secret,
access/refresh token) никогда не логируются.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bitrix_oauth import BitrixOAuthToken
from app.models.time import utc_now

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth.bitrix.info/oauth/token/"
_REST_TIMEOUT = 30.0


class BitrixOAuthError(Exception):
    """Ошибка обмена/обновления OAuth-токена Bitrix24."""


@dataclass(frozen=True)
class TokenPair:
    """Результат обмена/обновления токена."""

    access_token: str
    refresh_token: str
    expires_at: datetime


async def store_installation(
    session: AsyncSession,
    *,
    member_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> BitrixOAuthToken:
    """Сохраняет или обновляет токен установки по `member_id`."""
    expires_at = utc_now() + timedelta(seconds=expires_in)
    existing = await _get_token_row(session, member_id)
    if existing is None:
        existing = BitrixOAuthToken(
            member_id=member_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        session.add(existing)
    else:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
    await session.commit()
    logger.info("bitrix oauth установка сохранена member_id=%s", member_id)
    return existing


async def refresh_access_token(refresh_token: str) -> TokenPair:
    """Обменивает refresh_token на новую пару через oauth.bitrix.info."""
    params = {
        "grant_type": "refresh_token",
        "client_id": settings.bitrix_client_id,
        "client_secret": settings.bitrix_client_secret,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as client:
        try:
            response = await client.get(_TOKEN_URL, params=params)
        except httpx.HTTPError as exc:
            logger.warning("bitrix oauth refresh сетевой сбой: %s", exc)
            raise BitrixOAuthError("refresh_token: сетевой сбой") from exc
    data = response.json()
    if "error" in data:
        logger.warning("bitrix oauth refresh ошибка: %s", data.get("error"))
        raise BitrixOAuthError(f"refresh_token: {data.get('error')}")
    try:
        return TokenPair(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=utc_now() + timedelta(seconds=int(data["expires_in"])),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("bitrix oauth refresh неожиданный ответ")
        raise BitrixOAuthError("refresh_token: неожиданный формат ответа") from exc


async def get_current_access_token(session: AsyncSession) -> str | None:
    """Действующий access_token единственной установки (одна инсталляция

    Bitrix на процесс, см. Non-Goals в design.md); обновляет протухший токен.
    """
    stmt = select(BitrixOAuthToken).order_by(BitrixOAuthToken.updated_at.desc())
    row = (await session.scalars(stmt)).first()
    if row is None:
        return None
    if row.expires_at > utc_now():
        return row.access_token
    pair = await refresh_access_token(row.refresh_token)
    row.access_token = pair.access_token
    row.refresh_token = pair.refresh_token
    row.expires_at = pair.expires_at
    await session.commit()
    return row.access_token


async def _get_token_row(
    session: AsyncSession,
    member_id: str,
) -> BitrixOAuthToken | None:
    stmt = select(BitrixOAuthToken).where(BitrixOAuthToken.member_id == member_id)
    return (await session.scalars(stmt)).first()
