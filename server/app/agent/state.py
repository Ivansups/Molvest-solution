"""Состояние диалогового графа — общее для всех сценариев."""

from typing import Literal, TypedDict

Intent = Literal["empty", "handoff", "support", "greeting", "away", "offtopic"]


class RetrievedChunk(TypedDict):
    """Чанк базы знаний, найденный ретривалом."""

    document_id: str
    title: str
    chunk_text: str
    score: float


class HistoryTurn(TypedDict):
    """Короткая реплика из сохранённого диалога."""

    role: str
    content: str


class AgentState(TypedDict, total=False):
    """Накапливаемое состояние одного хода графа."""

    text: str | None
    image_base64: str | None
    installation_id: str | None
    query: str
    intent: Intent
    history: list[HistoryTurn]
    chunks: list[RetrievedChunk]
    kb_version: int
    answer: str
    confidence: float
    escalated: bool
    escalation_reason: str
    force_handoff: bool
