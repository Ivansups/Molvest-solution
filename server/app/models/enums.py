"""Доменные перечисления — в БД хранятся как строки."""

from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum_cls: type[StrEnum], *, length: int = 16) -> Enum:
    """VARCHAR с value enum, не с именем (OPEN ≠ open)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda items: [item.value for item in items],
    )


class FileType(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    DOC = "DOC"
    HTML = "HTML"
    MD = "MD"
    KB_CASE = "KB_CASE"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class ConversationStatus(StrEnum):
    OPEN = "open"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    OPERATOR = "operator"
