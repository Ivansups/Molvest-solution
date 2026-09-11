"""API и runtime-настройки: порог и режим эскалации."""

from collections.abc import AsyncIterator, Iterator
from typing import cast
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.nodes.retrieve import retrieve
from app.agent.state import AgentState, RetrievedChunk
from app.core.config import settings
from app.main import app
from app.services import runtime_settings


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture
async def settings_client() -> AsyncIterator[AsyncClient]:
    """Клиент без Postgres: /api/settings не трогает БД."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_get_settings_defaults(settings_client: AsyncClient) -> None:
    response = await settings_client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["confidence_threshold"] == pytest.approx(settings.confidence_threshold)
    assert body["operator_assist_mode"] == settings.operator_assist_mode


async def test_put_settings_and_readback(settings_client: AsyncClient) -> None:
    put = await settings_client.put(
        "/api/settings",
        json={"confidence_threshold": 0.9, "operator_assist_mode": "auto"},
    )
    assert put.status_code == 200
    assert put.json() == {
        "confidence_threshold": 0.9,
        "operator_assist_mode": "auto",
    }

    get = await settings_client.get("/api/settings")
    assert get.status_code == 200
    assert get.json()["operator_assist_mode"] == "auto"
    assert get.json()["confidence_threshold"] == pytest.approx(0.9)


async def test_put_settings_accepts_agent_mode(
    settings_client: AsyncClient,
) -> None:
    put = await settings_client.put(
        "/api/settings",
        json={"confidence_threshold": 0.8, "operator_assist_mode": "agent"},
    )
    assert put.status_code == 200
    assert put.json()["operator_assist_mode"] == "agent"

    get = await settings_client.get("/api/settings")
    assert get.status_code == 200
    assert get.json()["operator_assist_mode"] == "agent"


async def test_put_settings_rejects_unknown_assist_mode(
    settings_client: AsyncClient,
) -> None:
    before = (await settings_client.get("/api/settings")).json()
    response = await settings_client.put(
        "/api/settings",
        json={
            "confidence_threshold": 0.8,
            "operator_assist_mode": "require_operator_confirm",
        },
    )
    assert response.status_code == 422
    after = (await settings_client.get("/api/settings")).json()
    assert after == before


async def test_put_settings_rejects_invalid_threshold(
    settings_client: AsyncClient,
) -> None:
    before = (await settings_client.get("/api/settings")).json()
    response = await settings_client.put(
        "/api/settings",
        json={"confidence_threshold": 0.1, "operator_assist_mode": "draft"},
    )
    assert response.status_code == 422
    after = (await settings_client.get("/api/settings")).json()
    assert after == before


async def test_put_settings_ignores_unknown_fields(
    settings_client: AsyncClient,
) -> None:
    response = await settings_client.put(
        "/api/settings",
        json={
            "confidence_threshold": 0.85,
            "operator_assist_mode": "draft",
            "bitrixWebhook": "https://example.com/hook",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"confidence_threshold", "operator_assist_mode"}
    assert body["confidence_threshold"] == pytest.approx(0.85)


async def test_runtime_threshold_affects_retrieve_escalation() -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.95,
        operator_assist_mode="draft",
    )

    async def fake_retriever(_state: AgentState) -> list[RetrievedChunk]:
        return [
            {
                "document_id": str(uuid4()),
                "title": "doc",
                "chunk_text": "text",
                "score": 0.9,
            }
        ]

    state = cast(
        AgentState,
        {
            "query": "вопрос",
            "installation_id": str(uuid4()),
        },
    )
    result = await retrieve(state, retriever=fake_retriever)
    assert result["escalated"] is True
    assert result["confidence"] == pytest.approx(0.9)
