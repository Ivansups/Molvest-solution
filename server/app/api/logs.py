"""Read-only REST журнала операционных событий для админки."""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import require_internal_token
from app.db.session import SessionDep
from app.schemas.logs import (
    LogEventListOut,
    LogEventType,
    LogListParams,
)
from app.selectors import logs as log_selectors

router = APIRouter(
    prefix="/api/logs",
    tags=["logs"],
    dependencies=[Depends(require_internal_token)],
)

logger = logging.getLogger(__name__)


@router.get("")
async def list_logs_route(
    session: SessionDep,
    installation_id: UUID,
    event_type: LogEventType | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LogEventListOut:
    """Последние эскалации, закрытия диалогов и статусы индексации."""
    params = LogListParams(
        installation_id=installation_id,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    logger.info(
        "журнал installation_id=%s event_type=%s page=%s",
        installation_id,
        event_type,
        page,
    )
    rows, total = await log_selectors.list_operational_events(session, params)
    logger.info("журнал total=%s returned=%s", total, len(rows))
    return LogEventListOut(
        items=rows,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )
