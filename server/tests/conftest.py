"""Общие фикстуры тестов backend."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Chunk, Conversation, Document, Escalation, Message  # noqa: F401
from app.schemas.chat import ChatRequest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/molvest",
)
TEST_INTERNAL_SERVICE_TOKEN = "test-internal-service-token"


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


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Postgres для интеграционных тестов; skip, если БД не запущена."""
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
    except (OSError, OperationalError):
        await engine.dispose()
        pytest.skip("Postgres недоступен")
    yield engine
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(
        settings,
        "internal_service_token",
        TEST_INTERNAL_SERVICE_TOKEN,
    )

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {TEST_INTERNAL_SERVICE_TOKEN}"
        yield client
    app.dependency_overrides.clear()
