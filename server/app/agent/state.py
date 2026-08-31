"""Состояние диалогового графа — общее для всех сценариев."""

from typing import Literal, TypedDict

Intent = Literal["empty", "greeting", "off_topic", "support"]


class RetrievedChunk(TypedDict):
    """Чанк базы знаний, найденный ретривалом."""

    document_id: str
    title: str
    chunk_text: str
    score: float


class AgentState(TypedDict, total=False):
    """Накапливаемое состояние одного хода графа."""

    text: str | None
    image_base64: str | None
    installation_id: str | None
    query: str
    intent: Intent
    chunks: list[RetrievedChunk]
    answer: str
    confidence: float
    escalated: bool
