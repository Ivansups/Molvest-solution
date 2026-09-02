"""Чтение диалогов, их деталей и агрегированных метрик."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.models.conversation import Conversation
from app.models.escalation import Escalation
from app.models.message import Message
from app.schemas.conversations import ConversationListParams


async def list_conversations(
    session: AsyncSession,
    params: ConversationListParams,
) -> tuple[list[Conversation], int]:
    """Страница диалогов одной установки и общее число строк."""
    filters = [Conversation.installation_id == params.installation_id]
    if params.user_id is not None:
        filters.append(Conversation.user_id == params.user_id)
    if params.status is not None:
        filters.append(Conversation.status == params.status)
    if params.date_from is not None:
        filters.append(Conversation.created_at >= params.date_from)
    if params.date_to is not None:
        filters.append(Conversation.created_at <= params.date_to)

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
) -> Conversation | None:
    """Диалог с сообщениями и эскалациями или None."""
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.escalations),
        )
        .where(Conversation.id == conversation_id)
    )
    return (await session.scalars(stmt)).first()


async def get_messages(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[Message]:
    """Сообщения диалога по возрастанию времени."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list((await session.scalars(stmt)).all())


async def get_escalations(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[Escalation]:
    """Эскалации диалога."""
    stmt = (
        select(Escalation)
        .where(Escalation.conversation_id == conversation_id)
        .order_by(Escalation.id)
    )
    return list((await session.scalars(stmt)).all())


async def conversation_metrics(
    session: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, float | int]:
    """Агрегаты метрик: % автоответов, среднее время, число эскалаций."""
    message_filters: list[ColumnElement[bool]] = [
        Message.role.in_(("assistant", "system"))
    ]
    if date_from is not None:
        message_filters.append(Message.created_at >= date_from)
    if date_to is not None:
        message_filters.append(Message.created_at <= date_to)

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
        .where(*message_filters)
    )
    row = (await session.execute(auto_stmt)).one()
    total = int(row.total or 0)
    escalated_answers = int(row.escalated_answers or 0)
    auto_answer_percent = (
        round((total - escalated_answers) * 100.0 / total, 2) if total else 0.0
    )

    avg_response = await _avg_response_time_seconds(
        session,
        date_from=date_from,
        date_to=date_to,
    )

    escalation_filters = []
    if date_from is not None:
        escalation_filters.append(Conversation.created_at >= date_from)
    if date_to is not None:
        escalation_filters.append(Conversation.created_at <= date_to)
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
    date_from: datetime | None,
    date_to: datetime | None,
) -> float:
    """Среднее время от первого сообщения пользователя до ответа внутри диалога."""
    conversations_stmt = select(Conversation)
    if date_from is not None:
        conversations_stmt = conversations_stmt.where(
            Conversation.created_at >= date_from
        )
    if date_to is not None:
        conversations_stmt = conversations_stmt.where(
            Conversation.created_at <= date_to
        )
    conversations = list((await session.scalars(conversations_stmt)).all())

    durations: list[float] = []
    for conversation in conversations:
        msgs = await get_messages(session, conversation.id)
        user_times = [m.created_at for m in msgs if m.role == "user"]
        answer_times = [m.created_at for m in msgs if m.role in ("assistant", "system")]
        if not user_times or not answer_times:
            continue
        first_user = min(user_times)
        first_answer = min(answer_times)
        if first_answer > first_user:
            durations.append((first_answer - first_user).total_seconds())

    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 2)
