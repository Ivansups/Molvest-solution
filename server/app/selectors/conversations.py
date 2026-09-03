"""Чтение диалогов, их деталей и агрегированных метрик."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.conversation import Conversation
from app.models.enums import MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.schemas.conversations import ConversationListParams

_ANSWER_ROLES = (MessageRole.ASSISTANT, MessageRole.SYSTEM)


def _date_range_filters(
    column: ColumnElement[datetime],
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
) -> dict[str, float | int]:
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

    return {
        "auto_answer_percent": auto_answer_percent,
        "avg_response_time_seconds": avg_response,
        "escalation_count": escalation_count,
    }


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
        and row.first_answer > row.first_user
    ]

    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 2)
