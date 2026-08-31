"""Интеграционные тесты индексации и ретривала RAG-пайплайна."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import EMBEDDING_DIMENSIONS, Chunk
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.rag.chunking import (
    EMBEDDING_TOKEN_LIMIT,
    chunk_text,
    clamp_to_embedding_window,
    estimate_tokens,
    extract_text,
)
from app.rag.ingestion import IngestionError, index_document
from app.rag.protocols import (
    EmbeddingDimensionError,
    ensure_embedding_dimensions,
)
from app.rag.retrieval import retrieve_chunks

DIM = EMBEDDING_DIMENSIONS


def _embed(text: str) -> list[float]:
    """Детерминированный псевдовектор 1024d: похожие тексты — близкие векторы."""
    vec = [0.0] * DIM
    for char in text.lower():
        if char.isalpha():
            vec[ord(char) % DIM] += 1.0
    length = sum(v * v for v in vec) ** 0.5
    if length == 0:
        return vec
    return [v / length for v in vec]


class FakeEmbedder:
    """Заменяет GigaChatService: эмбеддинги без сети."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [_embed(text) for text in texts]


@pytest.fixture
def fake_llm() -> FakeEmbedder:
    return FakeEmbedder()


async def _indexed_document(
    db_session: AsyncSession,
    tmp_path: Path,
    *,
    body: str = (
        "Как провести документ в 1С. Откройте журнал документов и нажмите Провести."
    ),
    installation_id: UUID | None = None,
    **overrides: Any,
) -> Document:
    doc = Document(
        installation_id=installation_id or uuid4(),
        title=overrides.pop("title", "Инструкция"),
        file_name=overrides.pop("file_name", "guide.md"),
        file_type=overrides.pop("file_type", FileType.MD),
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    storage = tmp_path / f"{doc.id}.md"
    storage.write_text(body, encoding="utf-8")
    doc.extra_metadata = dict(doc.extra_metadata)
    doc.extra_metadata["storage_path"] = str(storage)
    await db_session.commit()
    return doc


# --- Chunking (без БД) ---


def test_chunk_text_short_is_single() -> None:
    chunks = chunk_text("один два три", max_chunk_size=512, chunk_overlap=128)
    assert chunks == ["один два три"]


def test_chunk_text_overlap_boundaries() -> None:
    text = " ".join(f"word{i}" for i in range(20))
    chunks = chunk_text(text, max_chunk_size=6, chunk_overlap=2)
    assert chunks[0] == "word0 word1 word2 word3 word4 word5"
    assert chunks[1] == "word4 word5 word6 word7 word8 word9"
    assert "word4 word5" in chunks[1]
    assert len(chunks) >= 4


def test_chunk_text_no_overlap_when_overlap_ge_size() -> None:
    text = " ".join(f"word{i}" for i in range(10))
    chunks = chunk_text(text, max_chunk_size=5, chunk_overlap=5)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_chunk_is_clamped_to_embedding_window() -> None:
    text = " ".join(f"слово{i}" for i in range(512))
    chunks = chunk_text(text, max_chunk_size=512, chunk_overlap=0)
    assert len(chunks) > 1
    limit = EMBEDDING_TOKEN_LIMIT - 40
    assert all(estimate_tokens(chunk) <= limit for chunk in chunks)


def test_clamp_keeps_short_chunk() -> None:
    assert clamp_to_embedding_window(["короткий текст"]) == ["короткий текст"]


def test_extract_text_markdown() -> None:
    text = extract_text("# Заголовок\nТело документа".encode(), FileType.MD)
    assert "Тело документа" in text


def test_extract_text_strips_html_tags() -> None:
    text = extract_text("<p>Привет <b>1С</b></p>".encode(), FileType.HTML)
    assert "Привет" in text
    assert "<p>" not in text


# --- Ingestion + Retrieval (Postgres) ---


async def test_index_creates_chunks_and_status(
    db_session: AsyncSession,
    tmp_path: Path,
    fake_llm: FakeEmbedder,
) -> None:
    doc = await _indexed_document(db_session, tmp_path)
    indexed = await index_document(db_session, doc, fake_llm)
    assert indexed.status == DocumentStatus.INDEXED

    count = await db_session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
    )
    assert count == 1


async def test_reindex_is_atomic_no_duplicate_chunks(
    db_session: AsyncSession,
    tmp_path: Path,
    fake_llm: FakeEmbedder,
) -> None:
    doc = await _indexed_document(db_session, tmp_path)
    await index_document(db_session, doc, fake_llm)
    await index_document(db_session, doc, fake_llm)

    count = await db_session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
    )
    assert count == 1


def test_ensure_embedding_dimensions_accepts_schema_size() -> None:
    ensure_embedding_dimensions([[0.0] * DIM])


def test_ensure_embedding_dimensions_rejects_mismatch() -> None:
    with pytest.raises(EmbeddingDimensionError, match="2560"):
        ensure_embedding_dimensions([[0.0] * 2560])


class _WrongDimEmbedder:
    """Имитирует стороннюю модель с другой размерностью (EmbeddingsGigaR)."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 2560 for _ in texts]


async def test_index_rejects_wrong_embedding_dim(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    doc = await _indexed_document(db_session, tmp_path)
    with pytest.raises(IngestionError, match="1024"):
        await index_document(db_session, doc, _WrongDimEmbedder())
    assert doc.status == DocumentStatus.FAILED
    assert "indexing_error" in doc.extra_metadata


async def test_retrieve_rejects_wrong_embedding_dim(
    db_session: AsyncSession,
    tmp_path: Path,
    fake_llm: FakeEmbedder,
) -> None:
    installation = uuid4()
    doc = await _indexed_document(db_session, tmp_path, installation_id=installation)
    await index_document(db_session, doc, fake_llm)
    with pytest.raises(EmbeddingDimensionError, match="2560"):
        await retrieve_chunks(
            db_session,
            query="как провести документ",
            installation_id=installation,
            llm=_WrongDimEmbedder(),
            top_k=5,
        )


async def test_index_failure_marks_failed(
    db_session: AsyncSession,
    tmp_path: Path,
    fake_llm: FakeEmbedder,
) -> None:
    doc = await _indexed_document(db_session, tmp_path, body="   ")
    with pytest.raises(IngestionError):
        await index_document(db_session, doc, fake_llm)
    assert doc.status == DocumentStatus.FAILED
    assert "indexing_error" in doc.extra_metadata


async def test_retrieve_returns_nearest_chunk(
    db_session: AsyncSession,
    tmp_path: Path,
    fake_llm: FakeEmbedder,
) -> None:
    installation = uuid4()
    doc = await _indexed_document(
        db_session,
        tmp_path,
        body=(
            "Как провести документ в 1С: откройте журнал документов, "
            "выберите нужный и нажмите кнопку Провести."
        ),
        installation_id=installation,
    )
    await index_document(db_session, doc, fake_llm)

    results = await retrieve_chunks(
        db_session,
        query="как провести документ",
        installation_id=installation,
        llm=fake_llm,
        top_k=5,
    )
    assert len(results) == 1
    assert results[0]["document_id"] == str(doc.id)
    assert "провести документ" in results[0]["chunk_text"]


async def test_retrieve_empty_when_nothing_indexed(
    db_session: AsyncSession,
    fake_llm: FakeEmbedder,
) -> None:
    results = await retrieve_chunks(
        db_session,
        query="что угодно",
        installation_id=uuid4(),
        llm=fake_llm,
        top_k=5,
    )
    assert results == []
