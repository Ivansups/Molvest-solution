"""Загрузка локальных файлов в БЗ: upload + атомарный reindex."""

from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.rag.protocols import EmbeddingsProvider
from app.selectors.documents import get_document_by_file_name
from app.services.documents import (
    ReindexFailedError,
    reindex_document,
    store_uploaded_bytes,
)

IngestResult = Literal["created", "skipped", "failed"]


async def ingest_local_file(
    session: AsyncSession,
    path: Path,
    *,
    installation_id: UUID,
    title: str | None = None,
    extra_metadata: dict[str, object] | None = None,
    llm: EmbeddingsProvider | None = None,
    app_settings: Settings | None = None,
) -> IngestResult:
    """Индексирует файл. Повтор с тем же именем — пропуск (не 409)."""
    file_name = path.name
    existing = await get_document_by_file_name(
        session,
        file_name,
        installation_id,
    )
    if existing is not None:
        return "skipped"

    document = await store_uploaded_bytes(
        session,
        file_name=file_name,
        data=path.read_bytes(),
        title=title or path.stem,
        installation_id=installation_id,
        extra_metadata=extra_metadata,
        app_settings=app_settings,
    )
    try:
        await reindex_document(
            session,
            document.id,
            installation_id,
            llm=llm,
            app_settings=app_settings,
        )
    except ReindexFailedError:
        return "failed"
    return "created"
