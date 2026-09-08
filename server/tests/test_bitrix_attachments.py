"""Юнит-тесты вложений Bitrix: url+id и fallback без Postgres."""

from unittest.mock import AsyncMock

import httpx
from pytest import MonkeyPatch

from app.channels.bitrix.attachments import fetch_attachment_base64, first_image_ref
from app.channels.bitrix.rest import Bitrix24RestError


def test_first_image_ref_keeps_file_id_when_url_present() -> None:
    url, file_id = first_image_ref(
        [{"url": "https://cdn.example/p.png", "id": "disk-77"}]
    )
    assert url == "https://cdn.example/p.png"
    assert file_id == "disk-77"


def test_first_image_ref_file_id_only() -> None:
    url, file_id = first_image_ref([{"fileId": "9"}])
    assert url is None
    assert file_id == "9"


async def test_fetch_falls_back_to_file_id_after_bad_url(
    monkeypatch: MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.download_image = AsyncMock(
        side_effect=Bitrix24RestError("вложение с недопустимого хоста: cdn.example")
    )
    client.download_file_by_id = AsyncMock(return_value="YWI=")
    monkeypatch.setattr(
        "app.channels.bitrix.attachments.get_current_access_token",
        AsyncMock(return_value="tok"),
    )
    result = await fetch_attachment_base64(
        client=client,
        session=AsyncMock(),
        url="https://cdn.example/p.png",
        file_id="77",
    )
    assert result == "YWI="
    client.download_file_by_id.assert_awaited()


async def test_fetch_http_error_without_file_id_returns_none() -> None:
    client = AsyncMock()
    request = httpx.Request("GET", "https://portal.bitrix24.ru/x")
    client.download_image = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "404",
            request=request,
            response=httpx.Response(404, request=request),
        )
    )
    result = await fetch_attachment_base64(
        client=client,
        session=AsyncMock(),
        url="https://portal.bitrix24.ru/x",
        file_id=None,
    )
    assert result is None
