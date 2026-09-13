"""Разбиение текста документа на перекрывающиеся чанки и извлечение текста."""

import io
import logging
import re
import struct

from app.models.enums import FileType

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\S+")
_TAG_RE = re.compile(r"<[^>]+>")
# script/style — не контент, а код/CSS: сам тег TAG_RE вырежет, а вот текст
# внутри него без этого попадёт в чанки и собьёт оценку токенов (длинные
# "слова" без пробелов — минифицированный JS).
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)

# Окно GigaChat Embeddings — 512 токенов (в ответе API бывает max 514).
EMBEDDING_TOKEN_LIMIT = 512
_TOKEN_MARGIN = 40
_CHARS_PER_TOKEN = 3
# Прогон реальной документации 1С показал реальное соотношение до ~10
# токенов/слово на плотном техническом русском тексте (числа, термины) —
# прежние 2 и даже 8 систематически занижали оценку и не спасали от
# 413 Tokens limit exceeded. Берём с запасом.
_TOKENS_PER_WORD = 14


def estimate_tokens(text: str) -> int:
    """Консервативная оценка токенов без токенизатора Сбера.

    Берём максимум из оценки по словам и по символам — так не проваливаемся
    ни на обычном тексте с длинными терминами, ни на слипшемся куске без
    пробелов (типичный сбой pypdf).
    """
    words = _WORD_RE.findall(text)
    word_estimate = len(words) * _TOKENS_PER_WORD
    char_estimate = (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN
    return max(word_estimate, char_estimate)


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
    if file_type in (FileType.MD, FileType.KB_CASE):
        return data.decode("utf-8", errors="replace")
    if file_type == FileType.HTML:
        html = data.decode("utf-8", errors="replace")
        html = _SCRIPT_STYLE_RE.sub(" ", html)
        return _TAG_RE.sub(" ", html)
    if file_type == FileType.PDF:
        return _extract_pdf(data)
    if file_type == FileType.DOCX:
        return _extract_docx(data)
    if file_type == FileType.DOC:
        return _extract_doc(data)
    raise ValueError(f"неподдерживаемый тип файла: {file_type}")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


_DOC_CONVERT_HINT = (
    "не удалось извлечь текст из .doc (Word 97–2003). "
    "Сохраните файл как .docx и загрузите снова"
)
_WORD_MAGIC = 0xA5EC
_FIB_FLAGS = 0x0A
_FIB_FC_MIN = 0x18
_FIB_FC_MAC = 0x1C
_FIB_ENCRYPTED = 0x0100
# Файл сохранён инкрементально (fast save): текст раздроблен piece table
# в 0Table/1Table, а не лежит одним куском в [fcMin:fcMac) — наш парсер
# такое не разбирает, лучше явно отказать, чем молча отдать перепутанный текст.
_FIB_COMPLEX = 0x0004


def _extract_doc(data: bytes) -> str:
    """Текст из OLE Word 97–2003. Иначе понятная ошибка — конвертировать в DOCX."""
    import olefile  # type: ignore[import-untyped]

    buffer = io.BytesIO(data)
    if not olefile.isOleFile(buffer):
        raise ValueError(_DOC_CONVERT_HINT)
    buffer.seek(0)
    ole = olefile.OleFileIO(buffer)
    try:
        if not ole.exists("WordDocument"):
            raise ValueError(_DOC_CONVERT_HINT)
        word = ole.openstream("WordDocument").read()
    finally:
        ole.close()
    if len(word) < 32 or struct.unpack_from("<H", word, 0)[0] != _WORD_MAGIC:
        raise ValueError(_DOC_CONVERT_HINT)
    flags = struct.unpack_from("<H", word, _FIB_FLAGS)[0]
    if flags & _FIB_ENCRYPTED:
        raise ValueError("зашифрованный .doc не поддерживается; сохраните как .docx")
    if flags & _FIB_COMPLEX:
        raise ValueError(_DOC_CONVERT_HINT)
    fc_min = struct.unpack_from("<I", word, _FIB_FC_MIN)[0]
    fc_mac = struct.unpack_from("<I", word, _FIB_FC_MAC)[0]
    pieces: list[str] = []
    if fc_min < fc_mac <= len(word):
        decoded = _decode_doc_bytes(word[fc_min:fc_mac])
        if decoded.strip():
            pieces.append(decoded)
    if not pieces:
        utf16 = _utf16_runs(word)
        if utf16.strip():
            pieces.append(utf16)
    text = "\n".join(part for part in pieces if part.strip())
    if not text.strip():
        raise ValueError(_DOC_CONVERT_HINT)
    return text


def _decode_doc_bytes(raw: bytes) -> str:
    if len(raw) >= 2 and raw[1] == 0:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("cp1251", errors="replace")


def _utf16_runs(data: bytes, min_chars: int = 12) -> str:
    runs: list[str] = []
    index = 0
    while index + 1 < len(data):
        chars: list[str] = []
        cursor = index
        while cursor + 1 < len(data):
            code = data[cursor] | (data[cursor + 1] << 8)
            if 32 <= code < 0xD800 or code in (9, 10, 13):
                chars.append(chr(code))
                cursor += 2
            else:
                break
        if len(chars) >= min_chars:
            runs.append("".join(chars))
            index = cursor
        else:
            index += 1
    return "\n".join(runs)


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
