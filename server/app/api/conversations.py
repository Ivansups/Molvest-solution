"""Read-only REST для диалогов этапа 6: список и детали."""

import logging
from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import require_internal_token
from app.db.session import SessionDep
from app.models.enums import ConversationStatus
from app.schemas.conversations import (
    ConversationDetailOut,
    ConversationListOut,
    ConversationListParams,
    ConversationOut,
    MessageOut,
    OperatorActionIn,
    OperatorMessageIn,
    ResolveConversationIn,
    conversation_to_detail,
    conversation_to_out,
    message_to_out,
)
from app.selectors import conversations as conversation_selectors
from app.services.agent import ConversationConflictError
from app.services.operator import (
    ConversationNotFoundError,
    ResolveNotConfirmedError,
    add_operator_reply,
    generate_suggestion,
    resolve_conversation,
)

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
    logger.info(
        "карточка диалога готова conversation_id=%s messages=%s escalations=%s",
        conversation_id,
        len(conversation.messages),
        len(conversation.escalations),
    )
    return conversation_to_detail(
        conversation, conversation.messages, conversation.escalations
    )


def _raise_operator_http(
    exc: ConversationNotFoundError | ConversationConflictError,
) -> NoReturn:
    """404 если диалог чужой/отсутствует, 409 если статус не подходит."""
    if isinstance(exc, ConversationNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не найден",
        ) from None
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=exc.detail,
    ) from exc


@router.post("/{conversation_id}/messages")
async def add_operator_message_route(
    session: SessionDep,
    conversation_id: UUID,
    body: OperatorMessageIn,
) -> MessageOut:
    """Ответ оператора в эскалированный диалог."""
    logger.info(
        "ответ оператора conversation_id=%s installation_id=%s",
        conversation_id,
        body.installation_id,
    )
    try:
        message = await add_operator_reply(
            session,
            conversation_id=conversation_id,
            installation_id=body.installation_id,
            text=body.text,
        )
    except (ConversationNotFoundError, ConversationConflictError) as exc:
        _raise_operator_http(exc)
    return message_to_out(message)


@router.post("/{conversation_id}/resolve")
async def resolve_conversation_route(
    session: SessionDep,
    conversation_id: UUID,
    body: ResolveConversationIn,
) -> ConversationOut:
    """Закрывает эскалированный диалог после confirmed=true."""
    logger.info(
        "resolve conversation_id=%s installation_id=%s confirmed=%s",
        conversation_id,
        body.installation_id,
        body.confirmed,
    )
    try:
        conversation = await resolve_conversation(
            session,
            conversation_id=conversation_id,
            installation_id=body.installation_id,
            confirmed=body.confirmed,
            comment=body.comment,
        )
    except ResolveNotConfirmedError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Нужно подтверждение закрытия",
        ) from None
    except (ConversationNotFoundError, ConversationConflictError) as exc:
        _raise_operator_http(exc)
    return conversation_to_out(conversation)


@router.post("/{conversation_id}/suggest")
async def suggest_conversation_route(
    session: SessionDep,
    conversation_id: UUID,
    body: OperatorActionIn,
) -> ConversationDetailOut:
    """Считает черновик по кнопке оператора."""
    logger.info(
        "suggest conversation_id=%s installation_id=%s",
        conversation_id,
        body.installation_id,
    )
    try:
        conversation = await generate_suggestion(
            session,
            conversation_id=conversation_id,
            installation_id=body.installation_id,
        )
    except (ConversationNotFoundError, ConversationConflictError) as exc:
        _raise_operator_http(exc)
    return conversation_to_detail(
        conversation, conversation.messages, conversation.escalations
    )
