"""Вебхук бота открытой линии: ONIMBOTMESSAGEADD.

Fail-closed по токену приложения, как у коннектора. JSON и PHP-style form.
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.channels.bitrix.openlines import _validate_auth
from app.channels.bitrix.schemas import (
    BitrixBotEvent,
    BitrixBotResponse,
    BitrixOpenLinesEvent,
    php_form_to_mapping,
)
from app.db.session import SessionDep
from app.services.agent import ConversationConflictError
from app.services.ol_bot import process_bot_event

router = APIRouter(prefix="/webhook", tags=["bitrix"])

_MISSING_DIALOG_MSG = "Событие не содержит DIALOG_ID или MESSAGE_ID"


@router.post("/bitrix/bot", response_model=BitrixBotResponse)
async def bitrix_bot_webhook(
    request: Request,
    session: SessionDep,
) -> BitrixBotResponse:
    """Принимает событие бота и возвращает результат обработки."""
    event = await _read_event(request)
    _validate_auth(BitrixOpenLinesEvent(auth=event.auth))

    if _looks_like_question(event):
        params = event.data.PARAMS if event.data else None
        if params is None or params.DIALOG_ID is None or params.MESSAGE_ID is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_MISSING_DIALOG_MSG,
            )

    try:
        return await process_bot_event(session, event)
    except ConversationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.detail,
        ) from exc


async def _read_event(request: Request) -> BitrixBotEvent:
    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Тело события должно быть объектом",
            )
        return BitrixBotEvent.model_validate(payload)
    form = await request.form()
    mapping = php_form_to_mapping({str(key): str(value) for key, value in form.items()})
    return BitrixBotEvent.model_validate(mapping)


def _looks_like_question(event: BitrixBotEvent) -> bool:
    name = (event.event or "").upper()
    if name and name != "ONIMBOTMESSAGEADD":
        return False
    params = event.data.PARAMS if event.data else None
    if params is None:
        return False
    text = (params.MESSAGE or "").strip()
    return bool(text or params.FILES)
