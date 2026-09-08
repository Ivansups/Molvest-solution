"""Вебхук Redmine HelpDesk: внутренний токен, 403 без записи."""

from fastapi import APIRouter, HTTPException, Request, status

from app.channels.redmine.schemas import RedmineEvent, RedmineResponse
from app.core.security import assert_internal_token
from app.db.session import SessionDep
from app.services.agent import ConversationConflictError
from app.services.redmine import process_redmine_event

router = APIRouter(prefix="/webhook", tags=["redmine"])


@router.post("/redmine", response_model=RedmineResponse)
async def redmine_webhook(
    request: Request,
    event: RedmineEvent,
    session: SessionDep,
) -> RedmineResponse:
    assert_internal_token(
        request.headers.get("x-internal-token"),
        status_code=status.HTTP_403_FORBIDDEN,
    )
    try:
        return await process_redmine_event(session, event)
    except ConversationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from exc
