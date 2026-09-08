"""Вебхук входящих сообщений живого треда Bitrix."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.channels.bitrix.schemas import (
    BitrixWebhookEvent,
    BitrixWebhookResponse,
)
from app.core.security import require_internal_token
from app.db.session import SessionDep
from app.services.agent import ConversationConflictError
from app.services.live_thread import process_live_thread_event

router = APIRouter(
    prefix="/webhook",
    tags=["bitrix"],
    dependencies=[Depends(require_internal_token)],
)

logger = logging.getLogger(__name__)


@router.post("/bitrix", response_model=BitrixWebhookResponse)
async def bitrix_webhook(
    event: BitrixWebhookEvent,
    session: SessionDep,
) -> BitrixWebhookResponse:
    """Принимает сообщение живого треда и возвращает действие агента."""
    try:
        return await process_live_thread_event(session, event)
    except ConversationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from exc
