"""Тесты стартовых узлов и графа LangGraph на заглушке GigaChat."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.agent.graph import build_graph
from app.agent.nodes.route import route
from app.agent.parsing import parse_confidence, parse_intent
from app.agent.state import AgentState
from app.core.config import Settings
from app.schemas.chat import ChatRequest
from app.services.agent import run_chat_turn


def _state(**overrides: object) -> AgentState:
    base: AgentState = {
        "text": "Как провести документ?",
        "image_base64": None,
        "query": "",
        "intent": "empty",
        "chunks": [],
        "answer": "",
        "confidence": 0.0,
        "escalated": False,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


async def test_empty_input_skips_llm(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text=None, image_base64=None))
    assert result["intent"] == "empty"
    assert result["escalated"] is False
    llm_mock.generate.assert_not_called()
    llm_mock.chat_with_vision.assert_not_called()


async def test_greeting_skips_retrieve_and_confidence(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(
        side_effect=['{"intent": "greeting"}', "Здравствуйте!"]
    )
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="привет"))
    assert result["intent"] == "greeting"
    assert result["answer"] == "Здравствуйте!"
    assert result["confidence"] == 1.0
    assert result["escalated"] is False
    assert result["chunks"] == []
    assert llm_mock.generate.await_count == 2


async def test_support_escalates_below_threshold(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(
        side_effect=[
            '{"intent": "support"}',
            "Черновик ответа",
            '{"confidence": 0.4}',
        ]
    )
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state())
    assert result["intent"] == "support"
    assert result["answer"] == "Черновик ответа"
    assert result["confidence"] == 0.4
    assert result["escalated"] is True
    assert llm_mock.generate.await_count == 3


async def test_support_does_not_escalate_at_threshold(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(
        side_effect=[
            '{"intent": "support"}',
            "Ответ из базы",
            '{"confidence": 0.8}',
        ]
    )
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state())
    assert result["escalated"] is False
    assert result["confidence"] == 0.8


async def test_vision_enriches_query_then_classifies(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.chat_with_vision = AsyncMock(return_value="Ошибка 1С:8330, поле Договор")
    llm_mock.generate = AsyncMock(side_effect=['{"intent": "greeting"}', "ok"])
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="что это?", image_base64="AAA"))
    llm_mock.chat_with_vision.assert_awaited_once()
    assert "Ошибка 1С:8330" in result["query"]
    assert "что это?" in result["query"]


async def test_route_uses_settings_threshold_twice(app_settings: Settings) -> None:
    state: AgentState = {"confidence": 0.79}
    first = await route(state, settings=app_settings)
    merged: AgentState = {**state, "escalated": first["escalated"]}
    second = await route(merged, settings=app_settings)
    assert first == second == {"escalated": True}

    high = await route({"confidence": 0.8}, settings=app_settings)
    assert high == {"escalated": False}


async def test_parse_intent_unknown_becomes_support() -> None:
    assert parse_intent('{"intent": "greeting"}') == "greeting"
    assert parse_intent("не json") == "support"
    assert parse_intent('{"intent": "unknown"}') == "support"


async def test_parse_confidence_clamps_and_falls_back() -> None:
    assert parse_confidence('{"confidence": 1.4}') == 1.0
    assert parse_confidence('{"confidence": -1}') == 0.0
    assert parse_confidence("нет числа") == 0.0


async def test_run_chat_turn_maps_contract(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
) -> None:
    import app.services.agent as agent_service

    graph = build_graph(llm_mock, app_settings)
    llm_mock.generate = AsyncMock(
        side_effect=['{"intent": "support"}', "Ответ", '{"confidence": 0.9}']
    )
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request)
    assert response.message_id == chat_request.message_id
    assert response.text == "Ответ"
    assert response.confidence == 0.9
    assert response.escalated is False
    assert response.sources == []
    assert isinstance(response.conversation_id, UUID)
