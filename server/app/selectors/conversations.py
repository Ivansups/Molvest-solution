"""Чтение диалогов, их деталей и агрегированных метрик."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.conversation import Conversation
from app.models.enums import MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.schemas.conversations import (
    ConversationListParams,
    ConversationMetrics,
    MetricsDailyPoint,
)

_ANSWER_ROLES = (MessageRole.ASSISTANT, MessageRole.SYSTEM)


def _date_range_filters(
    column: ColumnElement[datetime] | InstrumentedAttribute[datetime],
    *,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[ColumnElement[bool]]:
    """Фильтры `>= date_from` / `<= date_to` для колонки, если границы заданы."""
    filters: list[ColumnElement[bool]] = []
    if date_from is not None:
        filters.append(column >= date_from)
    if date_to is not None:
        filters.append(column <= date_to)
    return filters


async def list_conversations(
    session: AsyncSession,
    params: ConversationListParams,
) -> tuple[list[Conversation], int]:
    """Страница диалогов одной установки и общее число строк."""
    filters = [
        Conversation.installation_id == params.installation_id,
        *_date_range_filters(
            Conversation.created_at,
            date_from=params.date_from,
            date_to=params.date_to,
        ),
    ]
    if params.user_id is not None:
        filters.append(Conversation.user_id == params.user_id)
    if params.status is not None:
        filters.append(Conversation.status == params.status)

    count_stmt = select(func.count()).select_from(Conversation).where(*filters)
    total = int(await session.scalar(count_stmt) or 0)

    offset = (params.page - 1) * params.page_size
    rows_stmt = (
        select(Conversation)
        .where(*filters)
        .order_by(Conversation.created_at.desc())
        .offset(offset)
        .limit(params.page_size)
    )
    rows = list((await session.scalars(rows_stmt)).all())
    return rows, total


async def list_recent_messages(
    session: AsyncSession,
    conversation_id: UUID,
    *,
    limit: int,
) -> list[Message]:
    """Последние реплики диалога в хронологическом порядке."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list((await session.scalars(stmt)).all())
    return list(reversed(rows))


async def get_conversation(
    session: AsyncSession,
    conversation_id: UUID,
    installation_id: UUID,
) -> Conversation | None:
    """Диалог с сообщениями и эскалациями, ограниченный своей установкой, или None."""
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.escalations),
        )
        .where(
            Conversation.id == conversation_id,
            Conversation.installation_id == installation_id,
        )
    )
    return (await session.scalars(stmt)).first()


async def conversation_metrics(
    session: AsyncSession,
    *,
    installation_id: UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ConversationMetrics:
    """Агрегаты метрик одной установки: % автоответов, среднее время, эскалации."""
    message_filters = [
        Message.role.in_(_ANSWER_ROLES),
        *_date_range_filters(Message.created_at, date_from=date_from, date_to=date_to),
    ]

    auto_stmt = (
        select(
            func.count().label("total"),
            func.sum(
                case(
                    (Message.escalated.is_(True), 1),
                    else_=0,
                )
            ).label("escalated_answers"),
        )
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.installation_id == installation_id, *message_filters)
    )
    row = (await session.execute(auto_stmt)).one()
    total = int(row.total or 0)
    escalated_answers = int(row.escalated_answers or 0)
    auto_answer_percent = (
        round((total - escalated_answers) * 100.0 / total, 2) if total else 0.0
    )

    avg_response = await _avg_response_time_seconds(
        session,
        installation_id=installation_id,
        date_from=date_from,
        date_to=date_to,
    )

    escalation_filters = [
        Conversation.installation_id == installation_id,
        *_date_range_filters(
            Conversation.created_at, date_from=date_from, date_to=date_to
        ),
    ]
    escalation_count_stmt = (
        select(func.count())
        .select_from(Escalation)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(*escalation_filters)
    )
    escalation_count = int(await session.scalar(escalation_count_stmt) or 0)
    auto_answer_count = total - escalated_answers

    return ConversationMetrics(
        auto_answer_percent=auto_answer_percent,
        avg_response_time_seconds=avg_response,
        escalation_count=escalation_count,
        answer_count=total,
        auto_answer_count=auto_answer_count,
        daily=await _daily_activity(
            session,
            installation_id=installation_id,
            date_from=date_from,
            date_to=date_to,
        ),
    )


def _as_date(value: datetime | date) -> date:
    """Приводит timestamp из БД к календарной дате."""
    if isinstance(value, datetime):
        return value.date()
    return value


async def _daily_activity(
    session: AsyncSession,
    *,
    installation_id: UUID,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[MetricsDailyPoint]:
    """Диалоги и эскалации по дням в том же окне, что и скалярные метрики."""
    day_col = cast(Conversation.created_at, Date)
    day_expr = day_col.label("day")
    day_filters = [
        Conversation.installation_id == installation_id,
        *_date_range_filters(
            Conversation.created_at, date_from=date_from, date_to=date_to
        ),
    ]

    conversations_stmt = (
        select(day_expr, func.count().label("total"))
        .where(*day_filters)
        .group_by(day_col)
    )
    escalations_stmt = (
        select(day_expr, func.count().label("total"))
        .select_from(Escalation)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .where(*day_filters)
        .group_by(day_col)
    )

    conversation_rows = (await session.execute(conversations_stmt)).all()
    escalation_rows = (await session.execute(escalations_stmt)).all()

    conversations_by_day = {
        _as_date(row.day): int(row.total) for row in conversation_rows
    }
    escalations_by_day = {_as_date(row.day): int(row.total) for row in escalation_rows}
    days = sorted(set(conversations_by_day) | set(escalations_by_day))
    return [
        MetricsDailyPoint(
            date=day_key,
            conversation_count=conversations_by_day.get(day_key, 0),
            escalation_count=escalations_by_day.get(day_key, 0),
        )
        for day_key in days
    ]


async def _avg_response_time_seconds(
    session: AsyncSession,
    *,
    installation_id: UUID,
    date_from: datetime | None,
    date_to: datetime | None,
) -> float:
    """Среднее время от первого сообщения пользователя до ответа внутри диалога.

    Одним сгруппированным запросом (без N+1 по числу диалогов): для каждого
    диалога берётся время первого user-сообщения и первого ответа.
    """
    first_user = func.min(
        case((Message.role == MessageRole.USER, Message.created_at))
    ).label("first_user")
    first_answer = func.min(
        case((Message.role.in_(_ANSWER_ROLES), Message.created_at))
    ).label("first_answer")

    stmt = (
        select(first_user, first_answer)
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.installation_id == installation_id,
            *_date_range_filters(
                Conversation.created_at, date_from=date_from, date_to=date_to
            ),
        )
        .group_by(Message.conversation_id)
    )
    rows = (await session.execute(stmt)).all()

    durations = [
        (row.first_answer - row.first_user).total_seconds()
        for row in rows
        if row.first_user is not None
        and row.first_answer is not None
        and row.first_answer >= row.first_user
    ]

    if not durations:
        return 0.0
    return float(round(sum(durations) / len(durations), 2))
