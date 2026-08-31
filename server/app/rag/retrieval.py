"""Векторный поиск чанков по базе знаний для запроса пользователя."""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid5

from sqlalchemy import Float, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState, RetrievedChunk
from app.core.config import Settings, settings
from app.core.logging import preview
from app.core.redis import get_cached_embeddings, set_cached_embeddings
from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.rag.protocols import EmbeddingsProvider, ensure_embedding_dimensions

logger = logging.getLogger(__name__)

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
            logger.warning("ретривер: нет installation_id")
            return []
        try:
            installation_id = UUID(raw_installation)
        except ValueError:
            logger.warning("ретривер: невалидный installation_id=%s", raw_installation)
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
    SELECT без изменения состояния. Используем кэш Redis для эмбеддингов.
    """
    if not query.strip():
        logger.info("поиск пропуск: пустой запрос")
        return []

    cached = await get_cached_embeddings(query)
    if cached is not None:
        logger.info("эмбеддинг запроса из кэша query=%s", preview(query))
        embedding = cached[0]
    else:
        logger.info("эмбеддинг запроса через GigaChat query=%s", preview(query))
        embedding = (await llm.get_embeddings([query]))[0]
    ensure_embedding_dimensions([embedding])
    if cached is None:
        await set_cached_embeddings(query, [embedding])
        logger.info("эмбеддинг запроса записан в кэш")

    distance_col = Chunk.embedding.cosine_distance(embedding).label("distance")
    stmt = (
        select(Chunk, Document.title, cast(distance_col, Float))
        .join(Document, Document.id == Chunk.document_id)
        .where(
            Document.installation_id == installation_id,
            Document.status == DocumentStatus.INDEXED,
        )
        .order_by(distance_col)
        .limit(top_k)
    )
    chunks: list[RetrievedChunk] = []
    for chunk, title, distance in (await session.execute(stmt)).all():
        chunks.append(
            RetrievedChunk(
                document_id=str(chunk.document_id),
                title=title,
                chunk_text=chunk.content,
                score=round(1.0 - float(distance), 4),
            )
        )
    top = chunks[0]["score"] if chunks else 0.0
    logger.info(
        "поиск готов installation_id=%s top_k=%s found=%s top_score=%s",
        installation_id,
        top_k,
        len(chunks),
        top,
    )
    return chunks
