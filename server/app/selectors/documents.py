"""Чтение документов и чанков."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.schemas.documents import DocumentListParams


async def list_documents(
    session: AsyncSession,
    params: DocumentListParams,
) -> tuple[list[Document], int]:
    """Страница документов одной установки и общее число строк."""
    filters = [Document.installation_id == params.installation_id]
    if params.status is not None:
        filters.append(Document.status == params.status)
    if params.file_type is not None:
        filters.append(Document.file_type == params.file_type)

    count_stmt = select(func.count()).select_from(Document).where(*filters)
    total = int(await session.scalar(count_stmt) or 0)

    offset = (params.page - 1) * params.page_size
    rows_stmt = (
        select(Document)
        .where(*filters)
        .order_by(Document.uploaded_at.desc())
        .offset(offset)
        .limit(params.page_size)
    )
    rows = list((await session.scalars(rows_stmt)).all())
    return rows, total


async def get_document(
    session: AsyncSession,
    document_id: UUID,
) -> Document | None:
    """Документ с чанками или None, если нет строки."""
    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id)
    )
    return (await session.scalars(stmt)).first()
