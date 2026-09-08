"""OAuth Bitrix24: установочный хендшейк, хранение и обновление токена
(imconnector/imbot требуют контекст приложения, см.
openspec/changes/bitrix24-channel/design.md, D8)."""

from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.channels.bitrix.oauth as oauth
from app.core.config import settings
from app.models.bitrix_oauth import BitrixOAuthToken
from app.models.time import utc_now

INSTALL_PATH = "/webhook/bitrix/install"


@pytest.fixture(autouse=True)
def _oauth_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "bitrix_client_id", "client-id")
    monkeypatch.setattr(settings, "bitrix_client_secret", "client-secret")


async def test_install_stores_token_pair(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await api_client.post(
        INSTALL_PATH,
        data={
            "DOMAIN": "portal.bitrix24.ru",
            "AUTH_ID": "access-1",
            "REFRESH_ID": "refresh-1",
            "AUTH_EXPIRES": "3600",
            "member_id": "member-1",
        },
    )
    assert response.status_code == 200
    assert "BX24.installFinish" in response.text

    row = (
        await db_session.scalars(
            select(BitrixOAuthToken).where(BitrixOAuthToken.member_id == "member-1")
        )
    ).first()
    assert row is not None
    assert row.access_token == "access-1"
    assert row.refresh_token == "refresh-1"


async def test_install_missing_fields_is_422(api_client: AsyncClient) -> None:
    response = await api_client.post(INSTALL_PATH, data={"DOMAIN": "portal"})
    assert response.status_code == 422


async def test_install_response_has_no_secrets(api_client: AsyncClient) -> None:
    response = await api_client.post(
        INSTALL_PATH,
        data={
            "AUTH_ID": "super-secret-access",
            "REFRESH_ID": "super-secret-refresh",
            "AUTH_EXPIRES": "3600",
            "member_id": "member-2",
        },
    )
    assert "super-secret-access" not in response.text
    assert "super-secret-refresh" not in response.text


async def test_get_current_access_token_returns_valid_token(
    db_session: AsyncSession,
) -> None:
    await oauth.store_installation(
        db_session,
        member_id="member-3",
        access_token="valid-token",
        refresh_token="refresh-3",
        expires_in=3600,
    )
    token = await oauth.get_current_access_token(db_session)
    assert token == "valid-token"


async def test_get_current_access_token_refreshes_expired(
    db_session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    row = BitrixOAuthToken(
        member_id="member-4",
        access_token="stale-token",
        refresh_token="refresh-4",
        expires_at=utc_now() - timedelta(seconds=1),
    )
    db_session.add(row)
    await db_session.commit()

    monkeypatch.setattr(
        oauth,
        "refresh_access_token",
        AsyncMock(
            return_value=oauth.TokenPair(
                access_token="fresh-token",
                refresh_token="fresh-refresh",
                expires_at=utc_now() + timedelta(hours=1),
            )
        ),
    )

    token = await oauth.get_current_access_token(db_session)
    assert token == "fresh-token"
    await db_session.refresh(row)
    assert row.refresh_token == "fresh-refresh"


async def test_get_current_access_token_none_without_installation(
    db_session: AsyncSession,
) -> None:
    assert await oauth.get_current_access_token(db_session) is None


async def test_refresh_access_token_error_raises(monkeypatch: MonkeyPatch) -> None:
    class _FakeResponse:
        def json(self) -> dict[str, str]:
            return {"error": "invalid_grant"}

    class _FakeClient:
        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: _FakeClient())

    with pytest.raises(oauth.BitrixOAuthError):
        await oauth.refresh_access_token("bad-refresh")
