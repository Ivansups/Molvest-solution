"""Read-only REST метрик этапа 6."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_service_token
from app.db.session import SessionDep
from app.schemas.conversations import ConversationMetrics
from app.selectors import conversations as conversation_selectors

router = APIRouter(
    prefix="/api",
    tags=["metrics"],
    dependencies=[Depends(require_internal_service_token)],
)

logger = logging.getLogger(__name__)


@router.get("/metrics")
async def metrics_route(
    session: SessionDep,
    installation_id: UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ConversationMetrics:
    """Агрегированные метрики диалогов установки: автоответы, время, эскалации."""
    logger.info(
        "метрики installation_id=%s date_from=%s date_to=%s",
        installation_id,
        date_from,
        date_to,
    )
    data = await conversation_selectors.conversation_metrics(
        session,
        installation_id=installation_id,
        date_from=date_from,
        date_to=date_to,
    )
    logger.info("метрики готовы %s", data)
    return ConversationMetrics(
        auto_answer_percent=float(data["auto_answer_percent"]),
        avg_response_time_seconds=float(data["avg_response_time_seconds"]),
        escalation_count=int(data["escalation_count"]),
    )
