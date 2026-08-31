"""Векторный поиск чанков по базе знаний для запроса пользователя."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState, RetrievedChunk
from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.rag.protocols import EmbeddingsProvider

Retriever = Callable[[AgentState], Awaitable[list[RetrievedChunk]]]

_WORKSPACE_NAMESPACE = UUID("41f7c1f7-0000-4f6e-9c6e-000000000001")


def workspace_to_installation_id(workspace_id: str) -> UUID:
    """Детерминированно мапит workspace_id в installation_id (UUID)."""
    return uuid5(_WORKSPACE_NAMESPACE, workspace_id)


def make_retriever(
    llm: EmbeddingsProvider,
    app_settings: Settings | None = None,
) -> Retriever:
    """Собирает ретривер для графа: сессия за вызов, инсталляция из state."""
    cfg = app_settings or settings

    async def retriever(state: AgentState) -> list[RetrievedChunk]:
        raw_installation = state.get("installation_id")
        if raw_installation is None:
            return []
        try:
            installation_id = UUID(raw_installation)
        except ValueError:
            return []
        async with SessionLocal() as session:
            return await retrieve_chunks(
                session,
                query=state.get("query") or "",
                installation_id=installation_id,
                llm=llm,
                top_k=cfg.top_k,
            )

    return retriever


async def retrieve_chunks(
    session: AsyncSession,
    *,
    query: str,
    installation_id: UUID,
    llm: EmbeddingsProvider,
    top_k: int,
) -> list[RetrievedChunk]:
    """Возвращает top_k ближайших чанков установки по косинусной близости.

    Эмбеддинг запроса получаем снаружи транзакции, сам поиск — единственный
    SELECT без изменения состояния.
    """
    if not query.strip():
        return []
    embedding = (await llm.get_embeddings([query]))[0]

    stmt = (
        select(Chunk, Document.title)
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Document.installation_id == installation_id,
            Document.status == DocumentStatus.INDEXED,
        )
        .order_by(Chunk.embedding.cosine_distance(embedding))
        .limit(top_k)
    )
    chunks: list[RetrievedChunk] = []
    for chunk, title in (await session.execute(stmt)).all():
        chunks.append(
            RetrievedChunk(
                document_id=str(chunk.document_id),
                title=title,
                chunk_text=chunk.content,
            )
        )
    return chunks
