"""Регистрация бота открытой линии после установки приложения.

`imbot.register` не идемпотентен: сначала ищем бота по CODE, иначе создаём.
Пустой `BITRIX_HANDLER_BASE_URL` — только warning, install не падает.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.rest import (
    Bitrix24RestClient,
    Bitrix24RestError,
    build_rest_client,
)
from app.core.config import settings
from app.models.bitrix_oauth import BitrixOAuthToken

logger = logging.getLogger(__name__)

_DEFAULT_BOT_NAME = "Молвест поддержка"


async def ensure_openlines_bot(
    session: AsyncSession,
    *,
    access_token: str,
) -> str | None:
    """Возвращает id бота: существующий по CODE или только что созданный."""
    handler_base = settings.bitrix_handler_base_url.strip()
    if not handler_base:
        logger.warning(
            "BITRIX_HANDLER_BASE_URL пуст: бот открытой линии не зарегистрирован"
        )
        return None
    if not (
        settings.bitrix_portal_url
        and settings.bitrix_app_user_id
        and settings.bitrix_app_token
    ):
        logger.warning("bitrix REST не сконфигурирован: бот не зарегистрирован")
        return None

    code = settings.bitrix_bot_code.strip() or "molvest_support"
    handler_url = f"{handler_base.rstrip('/')}/webhook/bitrix/bot"
    client = build_rest_client()
    try:
        bot_id = await _resolve_bot_id(
            client,
            access_token=access_token,
            code=code,
            handler_url=handler_url,
        )
    except (Bitrix24RestError, OSError) as exc:
        logger.warning("регистрация бота открытой линии не удалась: %s", exc)
        return None
    finally:
        await client.aclose()

    if bot_id is None:
        return None
    await _store_bot_id(session, bot_id)
    logger.info("bitrix ol bot готов code=%s", code)
    return bot_id


async def get_current_bot_id(session: AsyncSession) -> str | None:
    """id бота последней установки или None."""
    row = await _latest_token_row(session)
    if row is None or not row.openlines_bot_id:
        return None
    return row.openlines_bot_id


async def _resolve_bot_id(
    client: Bitrix24RestClient,
    *,
    access_token: str,
    code: str,
    handler_url: str,
) -> str | None:
    listed = await client.list_bots(access_token)
    existing = _bot_id_from_list(listed, code)
    if existing is not None:
        return existing
    created = await client.register_openlines_bot(
        code=code,
        handler_url=handler_url,
        name=_DEFAULT_BOT_NAME,
        access_token=access_token,
    )
    return _bot_id_from_register(created)


def _bot_id_from_list(payload: dict[str, object], code: str) -> str | None:
    result = payload.get("result")
    if isinstance(result, dict):
        for bot_id, info in result.items():
            found = _match_bot_code(info, code)
            if found and isinstance(info, dict):
                return str(info.get("ID") or info.get("id") or bot_id)
            if str(bot_id) == code:
                return str(bot_id)
    if isinstance(result, list):
        for info in result:
            if _match_bot_code(info, code) and isinstance(info, dict):
                return str(info.get("ID") or info.get("id") or "")
    return None


def _match_bot_code(info: object, code: str) -> bool:
    if not isinstance(info, dict):
        return False
    raw = info.get("CODE") or info.get("code")
    return str(raw) == code if raw is not None else False


def _bot_id_from_register(payload: dict[str, object]) -> str | None:
    result = payload.get("result")
    if isinstance(result, (int, str)) and str(result):
        return str(result)
    if isinstance(result, dict):
        for key in ("BOT_ID", "bot_id", "ID", "id"):
            value = result.get(key)
            if value is not None:
                return str(value)
    return None


async def _store_bot_id(session: AsyncSession, bot_id: str) -> None:
    row = await _latest_token_row(session)
    if row is None:
        return
    if row.openlines_bot_id == bot_id:
        return
    row.openlines_bot_id = bot_id
    await session.commit()


async def _latest_token_row(session: AsyncSession) -> BitrixOAuthToken | None:
    stmt = select(BitrixOAuthToken).order_by(BitrixOAuthToken.updated_at.desc())
    return (await session.scalars(stmt)).first()
