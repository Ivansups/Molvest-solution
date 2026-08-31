"""Индексация документа: чанкинг, эмбеддинги и запись в pgvector."""

import asyncio
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.time import utc_now
from app.rag.chunking import extract_chunks
from app.rag.protocols import EmbeddingsProvider


class IngestionError(Exception):
    """Индексация не удалась — `reindex` помечает документ FAILED."""


async def index_document(
    session: AsyncSession,
    document: Document,
    llm: EmbeddingsProvider,
    *,
    app_settings: Settings | None = None,
) -> Document:
    """Строит чанки документа и атомарно заменяет ими старые.

    Сначала внешний вызов эмбеддингов, затем транзакция удаления+вставки —
    чтобы retrieval не видел документ наполовину обновлённым.
    """
    cfg = app_settings or settings
    try:
        chunks = await _build_chunks(document, cfg)
        embeddings = await llm.get_embeddings(chunks)
    except Exception as exc:
        await _mark_failed(session, document, str(exc))
        raise IngestionError(str(exc)) from exc

    if len(embeddings) != len(chunks):
        message = "число эмбеддингов не совпадает с числом чанков"
        await _mark_failed(session, document, message)
        raise IngestionError(message)

    rows = [
        Chunk(
            document_id=document.id,
            content=content,
            embedding=embedding,
            chunk_index=index,
        )
        for index, (content, embedding) in enumerate(
            zip(chunks, embeddings, strict=True)
        )
    ]
    await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
    session.add_all(rows)
    document.status = DocumentStatus.INDEXED
    document.indexed_at = utc_now()
    await session.commit()
    await session.refresh(document)
    return document


async def _mark_failed(session: AsyncSession, document: Document, reason: str) -> None:
    document.status = DocumentStatus.FAILED
    document.indexed_at = utc_now()
    metadata = dict(document.extra_metadata)
    metadata["indexing_error"] = reason
    document.extra_metadata = metadata
    await session.commit()


async def _build_chunks(document: Document, cfg: Settings) -> list[str]:
    storage = document.extra_metadata.get("storage_path")
    if not isinstance(storage, str) or not storage:
        raise IngestionError("у документа нет пути к файлу")
    data = await asyncio.to_thread(Path(storage).read_bytes)
    if not data:
        raise IngestionError("файл пуст")
    chunks = await asyncio.to_thread(
        extract_chunks,
        data,
        document.file_type,
        max_chunk_size=cfg.max_chunk_size,
        chunk_overlap=cfg.chunk_overlap,
    )
    if not chunks:
        raise IngestionError("из документа не извлечён текст")
    return chunks
