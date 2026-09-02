"""Read-only REST метрик этапа 6."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.conversations import ConversationMetrics
from app.selectors import conversations as conversation_selectors

router = APIRouter(prefix="/api", tags=["metrics"])

logger = logging.getLogger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/metrics")
async def metrics_route(
    session: SessionDep,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ConversationMetrics:
    """Агрегированные метрики диалогов: автоответы, время, эскалации."""
    logger.info("метрики date_from=%s date_to=%s", date_from, date_to)
    data = await conversation_selectors.conversation_metrics(
        session,
        date_from=date_from,
        date_to=date_to,
    )
    logger.info("метрики готовы %s", data)
    return ConversationMetrics(
        auto_answer_percent=float(data["auto_answer_percent"]),
        avg_response_time_seconds=float(data["avg_response_time_seconds"]),
        escalation_count=int(data["escalation_count"]),
    )
