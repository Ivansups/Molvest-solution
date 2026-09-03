"""REST для админки базы знаний: список, загрузка, карточка, удаление, reindex."""

import json
import logging
from json import JSONDecodeError
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.core.gigachat_client import get_gigachat_service
from app.core.logging import request_id_var
from app.db.session import SessionDep, SessionLocal
from app.models.enums import DocumentStatus, FileType
from app.schemas.documents import (
    DocumentDetailOut,
    DocumentListOut,
    DocumentListParams,
    DocumentOut,
    document_to_detail,
    document_to_out,
)
from app.selectors import documents as document_selectors
from app.services.documents import (
    DocumentNotFoundError,
    DuplicateDocumentError,
    ReindexFailedError,
    UnsupportedFileTypeError,
    delete_document,
    reindex_document,
    upload_document,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])

logger = logging.getLogger(__name__)


@router.get("")
async def list_documents_route(
    session: SessionDep,
    installation_id: UUID,
    document_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    file_type: FileType | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentListOut:
    """Пагинированный список документов одной установки."""
    params = DocumentListParams(
        installation_id=installation_id,
        status=document_status,
        file_type=file_type,
        page=page,
        page_size=page_size,
    )
    logger.info(
        "список документов installation_id=%s status=%s file_type=%s "
        "page=%s page_size=%s",
        installation_id,
        document_status,
        file_type,
        page,
        page_size,
    )
    rows, total = await document_selectors.list_documents(session, params)
    logger.info("список документов total=%s returned=%s", total, len(rows))
    return DocumentListOut(
        items=[document_to_out(row) for row in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document_route(
    session: SessionDep,
    file: UploadFile,
    title: Annotated[str, Form()],
    installation_id: Annotated[UUID, Form()],
    metadata: Annotated[str | None, Form(examples=["{}"])] = None,
) -> DocumentOut:
    """Сохраняет файл и запись со статусом PENDING. Индексации нет."""
    logger.info(
        "загрузка title=%s installation_id=%s filename=%s",
        title,
        installation_id,
        file.filename,
    )
    try:
        extra = _parse_metadata(metadata)
        document = await upload_document(
            session,
            file=file,
            title=title,
            installation_id=installation_id,
            extra_metadata=extra,
        )
    except UnsupportedFileTypeError as exc:
        logger.warning("загрузка отклонена: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateDocumentError as exc:
        logger.warning("загрузка дубль: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        logger.warning("загрузка metadata: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    logger.info(
        "загрузка готова document_id=%s status=%s",
        document.id,
        document.status,
    )
    return document_to_out(document)


@router.get("/{document_id}")
async def get_document_route(
    session: SessionDep,
    document_id: UUID,
) -> DocumentDetailOut:
    """Карточка документа с чанками."""
    logger.info("карточка document_id=%s", document_id)
    document = await document_selectors.get_document(session, document_id)
    if document is None:
        logger.warning("карточка не найдена document_id=%s", document_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найден")
    logger.info(
        "карточка готова document_id=%s status=%s chunks=%s",
        document.id,
        document.status,
        len(document.chunks),
    )
    return document_to_detail(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_route(session: SessionDep, document_id: UUID) -> None:
    """Удаляет документ, чанки и файл на диске."""
    logger.info("удаление document_id=%s", document_id)
    try:
        await delete_document(session, document_id)
    except DocumentNotFoundError as exc:
        logger.warning("удаление: документ не найден document_id=%s", document_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    logger.info("удаление готово document_id=%s", document_id)


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document_route(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    document_id: UUID,
) -> DocumentOut:
    """Запускает реиндексацию в фоне и сразу возвращает документ."""
    logger.info("реиндекс принят document_id=%s", document_id)
    document = await document_selectors.get_document(session, document_id)
    if document is None:
        logger.warning("реиндекс: документ не найден document_id=%s", document_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не найден")
    document.status = DocumentStatus.PENDING
    await session.commit()
    await session.refresh(document)
    background_tasks.add_task(
        _reindex_in_background,
        document_id,
        request_id_var.get(),
    )
    logger.info("реиндекс в фоне document_id=%s", document_id)
    return document_to_out(document)


async def _reindex_in_background(document_id: UUID, request_id: str) -> None:
    """Реиндексирует документ собственной сессией вне цикла запроса."""
    token = request_id_var.set(request_id)
    try:
        logger.info("фоновая реиндексация старт document_id=%s", document_id)
        try:
            async with SessionLocal() as session:
                await reindex_document(
                    session,
                    document_id,
                    llm=get_gigachat_service(),
                )
            logger.info("фоновая реиндексация готова document_id=%s", document_id)
        except ReindexFailedError:
            logger.warning(
                "фоновая реиндексация не удалась document_id=%s",
                document_id,
            )
    finally:
        request_id_var.reset(token)


def _parse_metadata(raw: str | None) -> dict[str, object]:
    # Swagger подставляет в optional Form слово "string" — это не JSON.
    stripped = "" if raw is None else raw.strip()
    if not stripped or stripped == "string":
        return {}
    try:
        parsed: object = json.loads(stripped)
    except JSONDecodeError as parse_error:
        raise ValueError("metadata должен быть JSON-объектом") from parse_error
    if not isinstance(parsed, dict):
        raise ValueError("metadata должен быть JSON-объектом")
    return parsed
