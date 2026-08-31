"""Разбиение текста документа на перекрывающиеся чанки и извлечение текста."""

import io
import re

from app.models.enums import FileType

_WORD_RE = re.compile(r"\S+")
_TAG_RE = re.compile(r"<[^>]+>")


def chunk_text(
    text: str,
    *,
    max_chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Делит текст на чанки до max_chunk_size слов с перекрытием chunk_overlap.

    Размер измеряется числом слов (пробелоразделённых токенов) — стабильная
    эвристика для коротких документов техподдержки без полного токенизатора.
    """
    words = _WORD_RE.findall(text)
    if not words:
        return []
    step = max(1, max_chunk_size - chunk_overlap)
    if chunk_overlap >= max_chunk_size:
        return [" ".join(words)]
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def extract_text(data: bytes, file_type: FileType) -> str:
    """Возвращает плоский текст документа по его типу."""
    if file_type == FileType.MD:
        return data.decode("utf-8", errors="replace")
    if file_type == FileType.HTML:
        return _TAG_RE.sub(" ", data.decode("utf-8", errors="replace"))
    if file_type == FileType.PDF:
        return _extract_pdf(data)
    if file_type == FileType.DOCX:
        return _extract_docx(data)
    raise ValueError(f"неподдерживаемый тип файла: {file_type}")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_chunks(
    data: bytes,
    file_type: FileType,
    *,
    max_chunk_size: int,
    chunk_overlap: int,
) -> list[str]:
    """Извлекает текст файла и режет его на чанки."""
    return chunk_text(
        extract_text(data, file_type),
        max_chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
    )
