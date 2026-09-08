"""Путь первоначальной установки локального приложения Bitrix24.

Bitrix шлёт сюда `ONAPPINSTALL` (form-urlencoded, PHP-style вложенные ключи
`auth[access_token]`, `auth[refresh_token]`, `auth[expires_in]`,
`auth[member_id]`) при установке/переустановке серверного локального
приложения. Формат подтверждён живым порталом (см.
openspec/changes/bitrix24-channel/design.md, D8) — отличается от более
старого плоского формата `AUTH_ID`/`REFRESH_ID`. Ответ должен завершить
установку вызовом `BX24.installFinish()`, иначе Bitrix считает её незавершённой.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.channels.bitrix.oauth import store_installation
from app.channels.bitrix.register_bot import ensure_openlines_bot
from app.db.session import SessionDep

router = APIRouter(prefix="/webhook", tags=["bitrix"])

logger = logging.getLogger(__name__)

_INSTALL_FINISH_HTML = """<!doctype html>
<html><head><script src="//api.bitrix24.com/api/v1/"></script></head>
<body><script>BX24.init(function(){ BX24.installFinish(); });</script></body>
</html>"""

_MISSING_FIELDS_MSG = (
    "Установка без auth[access_token]/auth[refresh_token]/"
    "auth[expires_in]/auth[member_id]"
)


@router.post("/bitrix/install", response_class=HTMLResponse)
async def bitrix_install(request: Request, session: SessionDep) -> HTMLResponse:
    """Принимает установочный вызов Bitrix и сохраняет пару OAuth-токенов."""
    form = await request.form()
    access_token = form.get("auth[access_token]")
    refresh_token = form.get("auth[refresh_token]")
    expires_in = form.get("auth[expires_in]")
    member_id = form.get("auth[member_id]")
    if not (access_token and refresh_token and expires_in and member_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_MISSING_FIELDS_MSG,
        )
    await store_installation(
        session,
        member_id=str(member_id),
        access_token=str(access_token),
        refresh_token=str(refresh_token),
        expires_in=int(str(expires_in)),
    )
    await ensure_openlines_bot(session, access_token=str(access_token))
    logger.info("bitrix install завершена member_id=%s", member_id)
    return HTMLResponse(content=_INSTALL_FINISH_HTML)
