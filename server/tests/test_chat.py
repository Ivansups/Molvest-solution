"""Контракт POST /chat после подключения графа."""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_session
from app.main import app
from app.schemas.chat import ChatRequest, ChatResponse


async def test_chat_returns_graph_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(request: ChatRequest, session: object) -> ChatResponse:
        return ChatResponse(
            conversation_id=request.conversation_id
            or UUID("22222222-2222-2222-2222-222222222222"),
            message_id=request.message_id,
            text="из графа",
            confidence=0.91,
            escalated=False,
            sources=[],
        )

    async def override_session() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr("app.api.chat.run_chat_turn", fake_run)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={
                "message_id": "11111111-1111-1111-1111-111111111111",
                "workspace_id": "demo",
                "conversation_id": None,
                "text": "Как провести документ?",
                "image_base64": None,
                "user_id": "u1",
            },
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "из графа"
    assert body["confidence"] == 0.91
    assert body["escalated"] is False
