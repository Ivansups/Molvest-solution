"""Чтение журнала: эскалации, закрытия диалогов, статус индексации."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.logging import preview
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.models.escalation import Escalation
from app.models.message import Message
from app.schemas.logs import LogEventOut, LogEventType, LogListParams

_MESSAGE_LIMIT = 160


def _date_range_filters(
    column: (
        ColumnElement[datetime]
        | InstrumentedAttribute[datetime]
        | InstrumentedAttribute[datetime | None]
    ),
    *,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[ColumnElement[bool]]:
    """Фильтры `>= date_from` / `<= date_to`, если границы заданы."""
    filters: list[ColumnElement[bool]] = []
    if date_from is not None:
        filters.append(column >= date_from)
    if date_to is not None:
        filters.append(column <= date_to)
    return filters


async def list_operational_events(
    session: AsyncSession,
    params: LogListParams,
) -> tuple[list[LogEventOut], int]:
    """Собирает события установки из уже существующих таблиц."""
    wanted = {params.event_type} if params.event_type is not None else set(LogEventType)
    events: list[LogEventOut] = []
    if LogEventType.ESCALATION in wanted:
        events.extend(await _escalation_events(session, params))
    if LogEventType.CONVERSATION_RESOLVED in wanted:
        events.extend(await _resolved_events(session, params))
    if wanted & {LogEventType.DOCUMENT_INDEXED, LogEventType.DOCUMENT_FAILED}:
        events.extend(await _document_events(session, params, wanted))

    events.sort(key=lambda item: (item.occurred_at, item.id), reverse=True)
    total = len(events)
    start = (params.page - 1) * params.page_size
    return events[start : start + params.page_size], total


async def _escalation_events(
    session: AsyncSession,
    params: LogListParams,
) -> list[LogEventOut]:
    stmt = (
        select(Escalation, Message.created_at)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .join(Message, Message.id == Escalation.message_id)
        .where(
            Conversation.installation_id == params.installation_id,
            *_date_range_filters(
                Message.created_at,
                date_from=params.date_from,
                date_to=params.date_to,
            ),
        )
    )
    rows = (await session.execute(stmt)).all()
    return [
        LogEventOut(
            id=f"{LogEventType.ESCALATION}:{escalation.id}",
            occurred_at=occurred_at,
            event_type=LogEventType.ESCALATION,
            conversation_id=escalation.conversation_id,
            document_id=None,
            message=_short_message(escalation.reason, "Диалог передан оператору"),
        )
        for escalation, occurred_at in rows
    ]


async def _resolved_events(
    session: AsyncSession,
    params: LogListParams,
) -> list[LogEventOut]:
    occurred_at = Conversation.resolve_confirmed_at
    stmt = select(Conversation).where(
        Conversation.installation_id == params.installation_id,
        occurred_at.is_not(None),
        *_date_range_filters(
            occurred_at,
            date_from=params.date_from,
            date_to=params.date_to,
        ),
    )
    rows = list((await session.scalars(stmt)).all())
    events: list[LogEventOut] = []
    for conversation in rows:
        closed_at = conversation.resolve_confirmed_at
        if closed_at is None:
            continue
        events.append(
            LogEventOut(
                id=f"{LogEventType.CONVERSATION_RESOLVED}:{conversation.id}",
                occurred_at=closed_at,
                event_type=LogEventType.CONVERSATION_RESOLVED,
                conversation_id=conversation.id,
                document_id=None,
                message=_short_message(
                    conversation.resolve_comment,
                    "Диалог закрыт",
                ),
            )
        )
    return events


async def _document_events(
    session: AsyncSession,
    params: LogListParams,
    wanted: set[LogEventType],
) -> list[LogEventOut]:
    statuses: list[DocumentStatus] = []
    if LogEventType.DOCUMENT_INDEXED in wanted:
        statuses.append(DocumentStatus.INDEXED)
    if LogEventType.DOCUMENT_FAILED in wanted:
        statuses.append(DocumentStatus.FAILED)
    occurred_at = Document.indexed_at
    stmt = select(Document).where(
        Document.installation_id == params.installation_id,
        Document.status.in_(statuses),
        occurred_at.is_not(None),
        *_date_range_filters(
            occurred_at,
            date_from=params.date_from,
            date_to=params.date_to,
        ),
    )
    rows = list((await session.scalars(stmt)).all())
    events: list[LogEventOut] = []
    for document in rows:
        stamped = document.indexed_at
        if stamped is None:
            continue
        if document.status == DocumentStatus.INDEXED:
            event_type = LogEventType.DOCUMENT_INDEXED
            message = f"Документ проиндексирован: {document.title}"
        else:
            event_type = LogEventType.DOCUMENT_FAILED
            error = _indexing_error(document)
            message = error or f"Индексация не удалась: {document.title}"
        events.append(
            LogEventOut(
                id=f"{event_type}:{document.id}",
                occurred_at=stamped,
                event_type=event_type,
                conversation_id=None,
                document_id=document.id,
                message=_short_message(message, message),
            )
        )
    return events


def _short_message(text: str | None, fallback: str) -> str:
    raw = (text or "").strip() or fallback
    return preview(raw, limit=_MESSAGE_LIMIT)


def _indexing_error(document: Document) -> str | None:
    raw = document.extra_metadata.get("indexing_error")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
