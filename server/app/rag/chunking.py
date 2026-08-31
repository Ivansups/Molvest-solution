"""Разбиение текста документа на перекрывающиеся чанки и извлечение текста."""

import io
import logging
import re

from app.models.enums import FileType

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\S+")
_TAG_RE = re.compile(r"<[^>]+>")

# Окно GigaChat Embeddings — 512 токенов (в ответе API бывает max 514).
EMBEDDING_TOKEN_LIMIT = 512
_TOKEN_MARGIN = 40
_CHARS_PER_TOKEN = 3
_TOKENS_PER_WORD = 2


def estimate_tokens(text: str) -> int:
    """Грубая оценка токенов без токенизатора Сбера.

    Для обычного текста — по словам (у 512 слов API вернул ~900 токенов).
    По символам — только слипшийся кусок без пробелов (типичный сбой pypdf).
    """
    words = _WORD_RE.findall(text)
    if len(words) <= 1:
        return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN
    return len(words) * _TOKENS_PER_WORD


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
        return clamp_to_embedding_window([" ".join(words)])
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return clamp_to_embedding_window(chunks)


def clamp_to_embedding_window(chunks: list[str]) -> list[str]:
    """Дробит куски, которые не влезут в POST /embeddings."""
    limit = EMBEDDING_TOKEN_LIMIT - _TOKEN_MARGIN
    fitted: list[str] = []
    for chunk in chunks:
        fitted.extend(_split_until_fits(chunk, limit))
    return fitted


def _split_until_fits(text: str, token_limit: int) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    if estimate_tokens(stripped) <= token_limit:
        return [stripped]
    words = _WORD_RE.findall(stripped)
    if len(words) <= 1:
        step = max(1, token_limit * _CHARS_PER_TOKEN)
        return [stripped[i : i + step] for i in range(0, len(stripped), step)]
    max_words = max(1, token_limit // _TOKENS_PER_WORD)
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]


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
    text = extract_text(data, file_type)
    chunks = chunk_text(
        text,
        max_chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
    )
    logger.info(
        "чанкинг type=%s bytes=%s chars=%s chunks=%s max_chunk_size=%s overlap=%s",
        file_type.value,
        len(data),
        len(text),
        len(chunks),
        max_chunk_size,
        chunk_overlap,
    )
    return chunks
