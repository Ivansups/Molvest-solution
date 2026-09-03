"""Проверка служебного токена и конверта ошибок."""

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.schemas.chat import ChatRequest, ChatResponse


async def _override_session() -> AsyncIterator[None]:
    yield None


@pytest.mark.asyncio
async def test_chat_requires_token_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json=chat_request.model_dump(mode="json"),
        )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "http_error"
    assert body["request_id"]
    assert response.headers.get("x-request-id") == body["request_id"]


@pytest.mark.asyncio
async def test_health_stays_public_when_token_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "secret")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_empty_token_skips_check(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "")

    async def fake_run(request: ChatRequest, session: object) -> ChatResponse:
        del session
        return ChatResponse(
            conversation_id=UUID("22222222-2222-2222-2222-222222222222"),
            message_id=request.message_id,
            text="ок",
            confidence=1.0,
            escalated=False,
            sources=[],
        )

    app.dependency_overrides[get_session] = _override_session
    monkeypatch.setattr("app.api.chat.run_chat_turn", fake_run)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json=chat_request.model_dump(mode="json"),
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["text"] == "ок"


@pytest.mark.asyncio
async def test_valid_token_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "secret")

    async def fake_run(request: ChatRequest, session: object) -> ChatResponse:
        del session
        return ChatResponse(
            conversation_id=UUID("22222222-2222-2222-2222-222222222222"),
            message_id=request.message_id,
            text="ок",
            confidence=1.0,
            escalated=False,
            sources=[],
        )

    app.dependency_overrides[get_session] = _override_session
    monkeypatch.setattr("app.api.chat.run_chat_turn", fake_run)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/chat",
                json=chat_request.model_dump(mode="json"),
                headers={"X-Internal-Token": "secret"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200


async def test_http_error_uses_envelope(api_client: AsyncClient) -> None:
    response = await api_client.get(f"/api/documents/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "http_error"
    assert body["detail"]
    assert body["request_id"]
    assert response.headers.get("x-request-id") == body["request_id"]


@pytest.mark.asyncio
async def test_unhandled_error_hides_stack(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("секретный стек")

    monkeypatch.setattr("app.api.documents.document_selectors.get_document", boom)
    response = await api_client.get(f"/api/documents/{uuid4()}")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert "секретный" not in body["detail"]
    assert body["request_id"]
