"""Юнит-тесты REST Bitrix: disk.file.get и im.notify (не гостевой send)."""

import json

import httpx
import pytest

from app.channels.bitrix.rest import Bitrix24RestClient, Bitrix24RestError
from app.core.config import settings

PORTAL = "https://portal.bitrix24.ru"


async def test_download_file_by_id_uses_oauth_and_portal_host(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured[str(request.url)] = request.method
        if "disk.file.get" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "DOWNLOAD_URL": "https://portal.bitrix24.ru/disk/file.bin"
                    }
                },
            )
        return httpx.Response(200, content=b"PNGDATA")

    monkeypatch.setattr(settings, "bitrix_app_user_id", "42")
    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    encoded = await client.download_file_by_id(
        file_id="99", access_token="oauth-secret"
    )
    assert encoded
    urls = " ".join(captured)
    assert "disk.file.get" in urls
    assert "oauth-secret" in urls
    assert "webhook-secret" not in urls
    for record in caplog.records:
        if record.name.startswith("app."):
            assert "oauth-secret" not in record.message
            assert "webhook-secret" not in record.message
    await client.aclose()


async def test_download_file_by_id_rejects_foreign_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "disk.file.get" in str(request.url):
            return httpx.Response(
                200,
                json={"result": {"DOWNLOAD_URL": "https://evil.example/x"}},
            )
        return httpx.Response(200, content=b"nope")

    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Bitrix24RestError, match="недопустимого хоста"):
        await client.download_file_by_id(file_id="1", access_token="oauth-secret")
    await client.aclose()


async def test_download_file_by_id_rejects_foreign_host_without_token_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "oauth-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        if "disk.file.get" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "DOWNLOAD_URL": (
                            f"https://evil.example/x?auth={token}&file=abc"
                        )
                    }
                },
            )
        return httpx.Response(200, content=b"nope")

    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Bitrix24RestError, match="evil.example") as err:
        await client.download_file_by_id(file_id="1", access_token=token)
    assert token not in str(err.value)
    for record in caplog.records:
        if record.name.startswith("app."):
            assert token not in record.message
    await client.aclose()


async def test_download_image_http_error_is_rest_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "oauth-secret"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Bitrix24RestError, match="HTTP 404"):
        await client.download_image(
            f"https://portal.bitrix24.ru/disk/file.bin?auth={token}"
        )
    for record in caplog.records:
        if record.name.startswith("app."):
            assert token not in record.message
    await client.aclose()


async def test_rest_http_status_is_bitrix_error_without_token_in_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "oauth-secret"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "expired"})

    monkeypatch.setattr(settings, "bitrix_app_user_id", "42")
    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(Bitrix24RestError, match="HTTP 401") as err:
        await client.send_operator_note(
            dialog_id="chat-9",
            text="Черновик",
            access_token=token,
        )
    assert token not in str(err.value)
    for record in caplog.records:
        if record.name.startswith("app."):
            assert token not in record.message
    await client.aclose()


async def test_send_operator_note_uses_im_notify_not_guest_methods(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"result": True})

    monkeypatch.setattr(settings, "bitrix_app_user_id", "42")
    client = Bitrix24RestClient(
        portal_url=PORTAL, app_user_id="1", app_token="webhook-secret"
    )
    await client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await client.send_operator_note(
        dialog_id="chat-9",
        text="Черновик",
        access_token="oauth-secret",
    )
    assert "im.notify" in str(captured["url"])
    assert "imbot.message.add" not in str(captured["url"])
    assert "imconnector.send.messages" not in str(captured["url"])
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["to"] == "42"
    assert "chat-9" in str(body["message"])
    assert "oauth-secret" not in str(body)
    for record in caplog.records:
        if record.name.startswith("app."):
            assert "oauth-secret" not in record.message
    await client.aclose()
