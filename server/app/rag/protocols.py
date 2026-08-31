"""Контракт эмбеддера для RAG — безопасная альтернатива GigaChatService."""

from typing import Protocol


class EmbeddingsProvider(Protocol):
    """Умеет векторизовать списки текстов. Реализация — GigaChatService."""

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Возвращает по вектору на каждый текстовый фрагмент."""
        ...
