"""Контракт эмбеддера для RAG — безопасная альтернатива GigaChatService."""

from typing import Protocol

from app.models.chunk import EMBEDDING_DIMENSIONS


class EmbeddingsProvider(Protocol):
    """Умеет векторизовать списки текстов. Реализация — GigaChatService."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Возвращает по вектору на каждый текстовый фрагмент."""
        ...


class EmbeddingDimensionError(ValueError):
    """Провайдер вернул вектор, несовместимый с колонкой pgvector."""


def ensure_embedding_dimensions(embeddings: list[list[float]]) -> None:
    """Падает, если длина вектора не совпадает с chunks.embedding (1024)."""
    for index, vector in enumerate(embeddings):
        actual = len(vector)
        if actual != EMBEDDING_DIMENSIONS:
            raise EmbeddingDimensionError(
                f"эмбеддинг #{index}: {actual} координат, "
                f"ожидается {EMBEDDING_DIMENSIONS} "
                "(колонка chunks.embedding; смените модель или миграцию)"
            )
