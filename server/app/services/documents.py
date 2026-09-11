"""Загрузка, правка метаданных, удаление и реиндексация документов."""

import asyncio
import logging
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.gigachat_client import GigaChatService, get_gigachat_service
from app.core.redis import increment_kb_version
from app.models.document import Document
from app.models.enums import DocumentStatus, FileType
from app.rag.ingestion import IngestionError, index_document
from app.selectors.documents import get_document

logger = logging.getLogger(__name__)

_EXTENSIONS: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".html": FileType.HTML,
    ".htm": FileType.HTML,
    ".md": FileType.MD,
    ".markdown": FileType.MD,
}


class DocumentNotFoundError(Exception):
    """Документ с таким id отсутствует."""

    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"Документ {document_id} не найден")


class DuplicateDocumentError(Exception):
    """То же имя файла уже есть в этой установке."""

    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"Файл {file_name} уже загружен")


class UnsupportedFileTypeError(Exception):
    """Расширение не из списка PDF/DOCX/HTML/MD."""

    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        super().__init__(f"Тип файла {file_name} не поддерживается")


def file_type_from_name(file_name: str) -> FileType:
    """Определяет тип по расширению. Иначе UnsupportedFileTypeError."""
    suffix = Path(file_name).suffix.lower()
    try:
        return _EXTENSIONS[suffix]
    except KeyError as exc:
        raise UnsupportedFileTypeError(file_name) from exc


async def upload_document(
    session: AsyncSession,
    *,
    file: UploadFile,
    title: str,
    installation_id: UUID,
    extra_metadata: dict[str, object] | None = None,
    app_settings: Settings | None = None,
) -> Document:
    """Сохраняет строку PENDING и пишет файл на диск после commit."""
    cfg = app_settings or settings
    safe_name = Path(file.filename or "").name
    if not safe_name:
        raise UnsupportedFileTypeError(file.filename or "")
    file_type = file_type_from_name(safe_name)

    document = Document(
        installation_id=installation_id,
        title=title,
        file_name=safe_name,
        file_type=file_type,
        status=DocumentStatus.PENDING,
        extra_metadata=dict(extra_metadata or {}),
    )
    session.add(document)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DuplicateDocumentError(safe_name) from exc
    await session.refresh(document)

    dest = _storage_path(cfg.upload_dir, document)
    try:
        await asyncio.to_thread(dest.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(dest.write_bytes, await file.read())
    except OSError:
        await session.delete(document)
        await session.commit()
        raise

    stored = dict(document.extra_metadata)
    stored["storage_path"] = str(dest)
    document.extra_metadata = stored
    await session.commit()
    await session.refresh(document)
    logger.info(
        "файл сохранён document_id=%s path=%s",
        document.id,
        dest,
    )
    return document


async def update_document_metadata(
    session: AsyncSession,
    document_id: UUID,
    installation_id: UUID,
    *,
    title: str | None = None,
    extra_metadata: dict[str, object] | None = None,
) -> Document:
    """Меняет title и/или extra_metadata. Чанки, статус и kb_version не трогает."""
    document = await get_document(session, document_id, installation_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    if title is not None:
        document.title = title
    if extra_metadata is not None:
        # storage_path и indexing_error живут в том же JSON — не затираем их.
        merged = dict(document.extra_metadata)
        merged.update(extra_metadata)
        document.extra_metadata = merged
    await session.commit()
    await session.refresh(document)
    logger.info(
        "метаданные документа обновлены document_id=%s title=%s metadata=%s",
        document_id,
        title is not None,
        extra_metadata is not None,
    )
    return document


async def delete_document(
    session: AsyncSession,
    document_id: UUID,
    installation_id: UUID,
) -> None:
    """Удаляет документ (чанки каскадом) и файл, если он есть."""
    document = await get_document(session, document_id, installation_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    path = _path_from_metadata(document)
    await session.delete(document)
    await session.commit()
    await increment_kb_version()
    logger.info("документ удалён document_id=%s file=%s", document_id, path)
    if path is not None:
        await asyncio.to_thread(path.unlink, missing_ok=True)


async def reindex_document(
    session: AsyncSession,
    document_id: UUID,
    installation_id: UUID,
    *,
    llm: GigaChatService | None = None,
    app_settings: Settings | None = None,
) -> Document:
    """Индексирует документ: чанкит, эмбеддит и заменяет старые чанки."""
    document = await get_document(session, document_id, installation_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    logger.info("реиндекс сервиса document_id=%s", document_id)
    effective_llm = llm or get_gigachat_service()
    document.status = DocumentStatus.PENDING
    await session.commit()
    try:
        document = await index_document(
            session,
            document,
            effective_llm,
            app_settings=app_settings,
        )
    except IngestionError as exc:
        raise ReindexFailedError(str(exc)) from exc
    return document


class ReindexFailedError(Exception):
    """Индексация документа не удалась (см. поле indexing_error)."""


def _storage_path(upload_dir: str, document: Document) -> Path:
    return (
        Path(upload_dir)
        / str(document.installation_id)
        / str(document.id)
        / document.file_name
    )


def _path_from_metadata(document: Document) -> Path | None:
    raw = document.extra_metadata.get("storage_path")
    if isinstance(raw, str) and raw:
        return Path(raw)
    return None
