"""API и runtime-настройки: порог, режим и правила эскалации."""

from collections.abc import AsyncIterator, Iterator
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.retrieve import retrieve
from app.agent.nodes.router import DETECTOR_FAILURE_REASON, route_intent
from app.agent.state import AgentState, RetrievedChunk
from app.core.config import settings
from app.core.gigachat_client import GigaChatError, GigaChatService
from app.core.openrouter_client import OpenRouterClassifier, OpenRouterError
from app.db.session import get_session
from app.main import app
from app.services import runtime_settings

_RULE_FIELDS = (
    "escalate_on_detector_failure",
    "escalate_on_low_rag",
    "skip_low_rag_on_image",
    "escalate_on_guest_handoff",
)


def _payload(**overrides: object) -> dict[str, object]:
    """Полное тело PUT: порог, режим и правила эскалации."""
    body: dict[str, object] = {
        "confidence_threshold": 0.8,
        "operator_assist_mode": "draft",
        "escalate_on_detector_failure": True,
        "escalate_on_low_rag": True,
        "skip_low_rag_on_image": True,
        "escalate_on_guest_handoff": True,
    }
    body.update(overrides)
    return body


def _default_rules() -> dict[str, bool]:
    return {name: True for name in _RULE_FIELDS}


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture
async def settings_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """PUT пишет override в Postgres — переживает рестарт процесса API."""

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_get_settings_defaults(settings_client: AsyncClient) -> None:
    response = await settings_client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["confidence_threshold"] == pytest.approx(settings.confidence_threshold)
    assert body["operator_assist_mode"] == settings.operator_assist_mode
    for name in _RULE_FIELDS:
        assert body[name] is True


async def test_put_settings_survives_process_restart(
    settings_client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT пишет в Postgres — рестарт процесса не должен откатывать override."""
    put = await settings_client.put(
        "/api/settings",
        json=_payload(
            confidence_threshold=0.93,
            operator_assist_mode="agent",
            escalate_on_low_rag=False,
        ),
    )
    assert put.status_code == 200

    runtime_settings.reset_effective_settings()  # имитирует новый процесс API
    await runtime_settings.load_persisted_settings(db_session)

    snap = runtime_settings.get_effective_settings()
    assert snap.confidence_threshold == pytest.approx(0.93)
    assert snap.operator_assist_mode == "agent"
    assert snap.escalate_on_low_rag is False
    assert snap.escalate_on_detector_failure is True


async def test_put_settings_and_readback(settings_client: AsyncClient) -> None:
    put = await settings_client.put(
        "/api/settings",
        json=_payload(confidence_threshold=0.9, operator_assist_mode="auto"),
    )
    assert put.status_code == 200
    assert put.json() == {
        "confidence_threshold": 0.9,
        "operator_assist_mode": "auto",
        **_default_rules(),
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
        json=_payload(operator_assist_mode="agent"),
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
        json=_payload(operator_assist_mode="require_operator_confirm"),
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
        json=_payload(confidence_threshold=0.1),
    )
    assert response.status_code == 422
    after = (await settings_client.get("/api/settings")).json()
    assert after == before


async def test_put_settings_ignores_unknown_fields(
    settings_client: AsyncClient,
) -> None:
    response = await settings_client.put(
        "/api/settings",
        json=_payload(
            confidence_threshold=0.85,
            bitrixWebhook="https://example.com/hook",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "confidence_threshold",
        "operator_assist_mode",
        *_RULE_FIELDS,
    }
    assert body["confidence_threshold"] == pytest.approx(0.85)


async def test_put_settings_escalation_rules_readback(
    settings_client: AsyncClient,
) -> None:
    put = await settings_client.put(
        "/api/settings",
        json=_payload(
            escalate_on_detector_failure=False,
            escalate_on_low_rag=False,
            skip_low_rag_on_image=False,
            escalate_on_guest_handoff=False,
        ),
    )
    assert put.status_code == 200
    assert put.json()["escalate_on_detector_failure"] is False
    assert put.json()["escalate_on_low_rag"] is False
    assert put.json()["skip_low_rag_on_image"] is False
    assert put.json()["escalate_on_guest_handoff"] is False

    get = await settings_client.get("/api/settings")
    assert get.status_code == 200
    assert get.json()["escalate_on_detector_failure"] is False
    assert get.json()["escalate_on_low_rag"] is False
    assert get.json()["skip_low_rag_on_image"] is False
    assert get.json()["escalate_on_guest_handoff"] is False


@pytest.mark.parametrize("field", _RULE_FIELDS)
async def test_put_settings_rejects_invalid_escalation_rule(
    settings_client: AsyncClient, field: str
) -> None:
    before = (await settings_client.get("/api/settings")).json()
    response = await settings_client.put(
        "/api/settings",
        json=_payload(**{field: "yes"}),
    )
    assert response.status_code == 422
    after = (await settings_client.get("/api/settings")).json()
    assert after == before


async def test_put_settings_rejects_missing_escalation_rule(
    settings_client: AsyncClient,
) -> None:
    before = (await settings_client.get("/api/settings")).json()
    body = _payload()
    del body["escalate_on_low_rag"]
    response = await settings_client.put("/api/settings", json=body)
    assert response.status_code == 422
    after = (await settings_client.get("/api/settings")).json()
    assert after == before


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


async def test_runtime_low_rag_rule_can_disable_retrieve_escalation() -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
        escalate_on_low_rag=False,
    )

    async def empty_retriever(_state: AgentState) -> list[RetrievedChunk]:
        return []

    state = cast(AgentState, {"query": "вопрос", "installation_id": str(uuid4())})
    result = await retrieve(state, retriever=empty_retriever)
    assert result["escalated"] is False
    assert result["confidence"] == pytest.approx(0.0)


async def test_runtime_image_rule_can_escalate_screenshot() -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
        skip_low_rag_on_image=False,
    )

    async def empty_retriever(_state: AgentState) -> list[RetrievedChunk]:
        return []

    state = cast(
        AgentState,
        {
            "query": "что на скрине",
            "installation_id": str(uuid4()),
            "image_base64": "AAA",
        },
    )
    result = await retrieve(state, retriever=empty_retriever)
    assert result["escalated"] is True


def _failing_classifier() -> MagicMock:
    classifier = MagicMock(spec=OpenRouterClassifier)
    classifier.is_configured.return_value = True
    classifier.route = AsyncMock(side_effect=OpenRouterError("down"))
    return classifier


def _failing_llm() -> MagicMock:
    llm = MagicMock(spec=GigaChatService)
    llm.classify_handoff = AsyncMock(side_effect=GigaChatError("down"))
    return llm


async def test_runtime_detector_failure_rule_can_skip_escalation() -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
        escalate_on_detector_failure=False,
    )
    result = await route_intent(
        {"query": "Соедините с живым специалистом"},
        classifier=_failing_classifier(),
        llm=_failing_llm(),
    )
    assert result == {}


async def test_runtime_guest_handoff_rule_can_skip_escalation() -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
        escalate_on_guest_handoff=False,
    )
    classifier = MagicMock(spec=OpenRouterClassifier)
    classifier.is_configured.return_value = False
    classifier.route = AsyncMock()
    llm = MagicMock(spec=GigaChatService)
    llm.classify_handoff = AsyncMock()
    result = await route_intent(
        {"query": "позови оператора"},
        classifier=classifier,
        llm=llm,
    )
    assert result == {}
    classifier.route.assert_not_awaited()
    llm.classify_handoff.assert_not_awaited()


async def test_runtime_detector_failure_default_still_escalates() -> None:
    result = await route_intent(
        {"query": "Соедините с живым специалистом"},
        classifier=_failing_classifier(),
        llm=_failing_llm(),
    )
    assert result["escalated"] is True
    assert result["escalation_reason"] == DETECTOR_FAILURE_REASON
