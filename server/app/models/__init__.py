"""Доменные модели. Импорт здесь наполняет Base.metadata."""

from app.models.agent_settings import AgentSettings
from app.models.bitrix_oauth import BitrixOAuthToken
from app.models.channel import ChannelThread
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.escalation import Escalation
from app.models.message import Message

__all__ = [
    "AgentSettings",
    "BitrixOAuthToken",
    "ChannelThread",
    "Chunk",
    "Conversation",
    "Document",
    "Escalation",
    "Message",
]
