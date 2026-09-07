"""Доменные модели. Импорт здесь наполняет Base.metadata."""

from app.models.channel import ChannelThread
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.escalation import Escalation
from app.models.message import Message

__all__ = [
    "ChannelThread",
    "Chunk",
    "Conversation",
    "Document",
    "Escalation",
    "Message",
]
