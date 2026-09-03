"""Read-only REST для диалогов этапа 6: список и детали."""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import require_internal_token
from app.db.session import SessionDep
from app.models.enums import ConversationStatus
from app.schemas.conversations import (
    ConversationDetailOut,
    ConversationListOut,
    ConversationListParams,
    conversation_to_detail,
    conversation_to_out,
)
from app.selectors import conversations as conversation_selectors

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_internal_token)],
)

logger = logging.getLogger(__name__)


@router.get("")
async def list_conversations_route(
    session: SessionDep,
    installation_id: UUID,
    user_id: str | None = None,
    status_filter: Annotated[ConversationStatus | None, Query(alias="status")] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListOut:
    """Пагинированный список диалогов установки с фильтрами."""
    params = ConversationListParams(
        installation_id=installation_id,
        user_id=user_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    logger.info(
        "список диалогов installation_id=%s user_id=%s status=%s page=%s",
        installation_id,
        user_id,
        status_filter,
        page,
    )
    rows, total = await conversation_selectors.list_conversations(session, params)
    logger.info("список диалогов total=%s returned=%s", total, len(rows))
    return ConversationListOut(
        items=[conversation_to_out(row) for row in rows],
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get("/{conversation_id}")
async def get_conversation_route(
    session: SessionDep,
    conversation_id: UUID,
    installation_id: UUID,
) -> ConversationDetailOut:
    """Карточка диалога: сообщения и эскалации."""
    logger.info(
        "карточка диалога conversation_id=%s installation_id=%s",
        conversation_id,
        installation_id,
    )
    conversation = await conversation_selectors.get_conversation(
        session, conversation_id, installation_id
    )
    if conversation is None:
        logger.warning(
            "карточка диалога не найдена conversation_id=%s installation_id=%s",
            conversation_id,
            installation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не найден",
        )
    messages = sorted(conversation.messages, key=lambda m: m.created_at)
    escalations = sorted(conversation.escalations, key=lambda e: e.id)
    logger.info(
        "карточка диалога готова conversation_id=%s messages=%s escalations=%s",
        conversation_id,
        len(messages),
        len(escalations),
    )
    return conversation_to_detail(conversation, messages, escalations)
