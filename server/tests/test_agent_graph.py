"""Тесты стартовых узлов и графа LangGraph (classify правилами, скор ретривала)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.agent.graph import build_graph
from app.agent.nodes.classify import _EMPTY_REPLY, classify
from app.agent.state import AgentState, RetrievedChunk
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
    assert result["answer"] == _EMPTY_REPLY
    assert result["escalated"] is False
    llm_mock.generate.assert_not_called()
    llm_mock.chat_with_vision.assert_not_called()


async def test_greeting_skips_retrieve(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(return_value="Здравствуйте!")
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="привет"))
    assert result["intent"] == "greeting"
    assert result["answer"] == "Здравствуйте!"
    assert result["confidence"] == 1.0
    assert result["escalated"] is False
    assert result["chunks"] == []
    assert llm_mock.generate.await_count == 1


async def test_support_retrieves_then_generates(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(return_value="Ответ из базы")

    async def fake_retriever(state: AgentState) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(UUID(int=1)),
                title="Инструкция",
                chunk_text="провести документ в 1С",
                score=0.9,
            )
        ]

    graph = build_graph(llm_mock, app_settings, retriever=fake_retriever)
    result = await graph.ainvoke(_state())
    assert result["intent"] == "support"
    assert result["answer"] == "Ответ из базы"
    assert result["confidence"] == 0.9
    assert result["escalated"] is False
    assert llm_mock.generate.await_count == 1


async def test_support_below_threshold_escalates_without_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.generate = AsyncMock(return_value="никогда не вызван")

    async def fake_retriever(state: AgentState) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(UUID(int=2)),
                title="Инструкция",
                chunk_text="что-то не по делу",
                score=0.4,
            )
        ]

    graph = build_graph(llm_mock, app_settings, retriever=fake_retriever)
    result = await graph.ainvoke(_state())
    assert result["escalated"] is True
    assert result["confidence"] == 0.4
    assert result["answer"] == ""
    llm_mock.generate.assert_not_called()


async def test_support_no_chunks_escalates_without_generate(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    async def fake_retriever(state: AgentState) -> list[RetrievedChunk]:
        return []

    graph = build_graph(llm_mock, app_settings, retriever=fake_retriever)
    result = await graph.ainvoke(_state())
    assert result["escalated"] is True
    assert result["confidence"] == 0.0
    llm_mock.generate.assert_not_called()


async def test_vision_enriches_query_then_classifies(
    llm_mock: MagicMock, app_settings: Settings
) -> None:
    llm_mock.chat_with_vision = AsyncMock(return_value="Ошибка 1С:8330, поле Договор")
    graph = build_graph(llm_mock, app_settings)
    result = await graph.ainvoke(_state(text="что это?", image_base64="AAA"))
    llm_mock.chat_with_vision.assert_awaited_once()
    assert "что это?" in result["query"]


async def test_classify_rules() -> None:
    assert (await classify({"query": "привет!"}))["intent"] == "greeting"
    assert (await classify({"query": "спасибо"}))["intent"] == "greeting"
    assert (await classify({"query": "как провести документ"}))["intent"] == "support"
    assert (await classify({"query": "какая у вас погода"}))["intent"] == "off_topic"
    empty = await classify({"query": "   "})
    assert empty["intent"] == "empty"
    assert empty["answer"] == _EMPTY_REPLY


async def test_run_chat_turn_maps_contract(
    monkeypatch: pytest.MonkeyPatch,
    chat_request: ChatRequest,
    llm_mock: MagicMock,
    app_settings: Settings,
    reset_graph_singleton: None,
) -> None:
    import app.services.agent as agent_service

    async def fake_retriever(state: AgentState) -> list[RetrievedChunk]:
        return []

    graph = build_graph(llm_mock, app_settings, retriever=fake_retriever)
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)

    response = await run_chat_turn(chat_request)
    assert response.message_id == chat_request.message_id
    assert response.escalated is True
    assert response.confidence == 0.0
    assert response.sources == []
    assert isinstance(response.conversation_id, UUID)
