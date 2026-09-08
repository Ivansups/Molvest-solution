"""Best-effort заметка оператору Bitrix: не реплика гостю."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.oauth import get_current_access_token
from app.channels.bitrix.rest import (
    Bitrix24RestClient,
    Bitrix24RestError,
)

logger = logging.getLogger(__name__)


async def try_send_operator_note(
    session: AsyncSession,
    client: Bitrix24RestClient | None,
    *,
    dialog_id: str,
    text: str | None,
) -> None:
    """Нет клиента, текста или OAuth — тишина; сбой REST только в лог."""
    if client is None or not text:
        return
    access_token = await get_current_access_token(session)
    if access_token is None:
        logger.warning("bitrix приложение не установлено: заметка не ушла")
        return
    try:
        await client.send_operator_note(
            dialog_id=dialog_id,
            text=text,
            access_token=access_token,
        )
    except (Bitrix24RestError, OSError) as exc:
        logger.warning(
            "заметка оператору не доставлена dialog_id=%s: %s",
            dialog_id,
            exc,
        )
