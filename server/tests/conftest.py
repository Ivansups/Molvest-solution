"""Общие фикстуры тестов backend."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.gigachat_client import GigaChatService
from app.schemas.chat import ChatRequest


@pytest.fixture
def app_settings() -> Settings:
    return Settings(
        gigachat_api_key="test-key",
        gigachat_model="GigaChat-2",
        confidence_threshold=0.8,
    )


@pytest.fixture
def llm_mock() -> MagicMock:
    mock = MagicMock(spec=GigaChatService)
    mock.generate = AsyncMock(return_value="")
    mock.chat_with_vision = AsyncMock(return_value="")
    mock.get_embeddings = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def chat_request() -> ChatRequest:
    return ChatRequest(
        message_id=UUID("11111111-1111-1111-1111-111111111111"),
        workspace_id="demo",
        conversation_id=None,
        text="Как провести документ?",
        image_base64=None,
        user_id="u1",
    )


@pytest.fixture
def reset_graph_singleton() -> Iterator[None]:
    """Сбрасывает кэш графа между тестами, которые его трогают."""
    import app.agent.graph as graph_mod

    previous = graph_mod._graph
    graph_mod._graph = None
    yield
    graph_mod._graph = previous
