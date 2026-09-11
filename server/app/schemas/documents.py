"""Схемы ответов и фильтров для API документов."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.document import Document
from app.models.enums import DocumentStatus, FileType


class ChunkOut(BaseModel):
    """Чанк в карточке документа — без вектора."""

    id: UUID
    content: str
    chunk_index: int


class DocumentOut(BaseModel):
    """Документ без списка чанков."""

    id: UUID
    installation_id: UUID
    title: str
    file_name: str
    file_type: FileType
    status: DocumentStatus
    uploaded_at: datetime
    indexed_at: datetime | None
    metadata: dict[str, object]


class DocumentDetailOut(DocumentOut):
    """Документ вместе с чанками."""

    chunks: list[ChunkOut]


class DocumentListOut(BaseModel):
    """Страница списка документов."""

    items: list[DocumentOut]
    page: int
    page_size: int
    total: int


def document_to_out(document: Document) -> DocumentOut:
    """Собирает ответ API из модели (колонка metadata → поле metadata)."""
    return DocumentOut(
        id=document.id,
        installation_id=document.installation_id,
        title=document.title,
        file_name=document.file_name,
        file_type=document.file_type,
        status=document.status,
        uploaded_at=document.uploaded_at,
        indexed_at=document.indexed_at,
        metadata=document.extra_metadata,
    )


def document_to_detail(document: Document) -> DocumentDetailOut:
    """Карточка документа с чанками по возрастанию индекса."""
    chunks = sorted(document.chunks, key=lambda item: item.chunk_index)
    return DocumentDetailOut(
        **document_to_out(document).model_dump(),
        chunks=[
            ChunkOut(id=chunk.id, content=chunk.content, chunk_index=chunk.chunk_index)
            for chunk in chunks
        ],
    )


class DocumentListParams(BaseModel):
    """Параметры списка — для селектора."""

    installation_id: UUID
    status: DocumentStatus | None = None
    file_type: FileType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class DocumentPatchIn(BaseModel):
    """Частичное обновление title и metadata без реиндекса."""

    title: str | None = None
    metadata: dict[str, object] | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("title не может быть пустым")
        return stripped

    @model_validator(mode="after")
    def require_title_or_metadata(self) -> Self:
        if self.title is None and self.metadata is None:
            raise ValueError("нужно указать title и/или metadata")
        return self
