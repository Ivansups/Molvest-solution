"""Клиент Redis для кэширования эмбеддингов и ответов.

Redis — только оптимизация: при его недоступности кэш молча пропускается,
не ломая основной путь индексации, ретривала и генерации.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

from redis.asyncio import Redis

from app.core.config import settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Возвращает процесс-одиночку Redis."""
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _client


async def _best_effort(
    func: Callable[..., Awaitable[object]], *args: Any, **kwargs: Any
) -> Any:
    """Выполняет Redis-вызов, возвращая None при любой ошибке подключения."""
    try:
        return await func(*args, **kwargs)
    except Exception:
        return None


def hash_text(text: str) -> str:
    """SHA-256 нормализованного текста для ключей кэша."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


async def get_cached_embeddings(query: str) -> list[list[float]] | None:
    """Получает кэшированные эмбеддинги запроса (TTL ~1ч)."""
    raw = await _best_effort(get_redis().get, f"emb:{hash_text(query)}")
    if raw is None:
        return None
    return cast("list[list[float]]", json.loads(raw))


async def set_cached_embeddings(query: str, embeddings: list[list[float]]) -> None:
    """Сохраняет эмбеддинги в кэш (TTL 1 час)."""
    await _best_effort(
        get_redis().set,
        f"emb:{hash_text(query)}",
        json.dumps(embeddings),
        ex=3600,
    )


async def get_cached_answer(query: str, kb_version: int) -> str | None:
    """Получает кэшированный ответ (если БЗ не менялась)."""
    value = await _best_effort(get_redis().get, f"ans:{kb_version}:{hash_text(query)}")
    return value if isinstance(value, str) else None


async def set_cached_answer(query: str, answer: str, kb_version: int) -> None:
    """Сохраняет ответ в кэш (TTL 1 час)."""
    await _best_effort(
        get_redis().set,
        f"ans:{kb_version}:{hash_text(query)}",
        answer,
        ex=3600,
    )


async def get_kb_version() -> int:
    """Текущая версия базы знаний."""
    raw = await _best_effort(get_redis().get, "kb_version")
    return int(raw) if raw is not None else 0


async def increment_kb_version() -> int:
    """Инкрементирует версию БЗ при индексации/удалении документа."""
    value = await _best_effort(get_redis().incr, "kb_version")
    return int(value) if isinstance(value, int) else 1
