"""Разбор и скачивание вложения Bitrix: прямой URL или file id."""

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.oauth import get_current_access_token
from app.channels.bitrix.rest import Bitrix24RestClient, Bitrix24RestError

logger = logging.getLogger(__name__)

_FETCH_ERRORS = (Bitrix24RestError, OSError, httpx.HTTPError)


def first_image_ref(
    items: list[dict[str, object]],
) -> tuple[str | None, str | None]:
    """Первая картинка: url и/или file id с того же элемента."""
    for item in items:
        raw_url = item.get("url") or item.get("urlDownload") or item.get("link")
        url = raw_url if isinstance(raw_url, str) and raw_url else None
        raw_id = (
            item.get("id")
            or item.get("fileId")
            or item.get("FILE_ID")
            or item.get("file_id")
        )
        file_id = str(raw_id) if raw_id else None
        if url or file_id:
            return url, file_id
    return None, None


async def fetch_attachment_base64(
    *,
    client: Bitrix24RestClient | None,
    session: AsyncSession,
    url: str | None,
    file_id: str | None,
) -> str | None:
    """Best-effort: url, при сбое — disk.file.get. Исключение наружу не идёт."""
    if client is None:
        return None
    if url:
        try:
            return await client.download_image(url)
        except _FETCH_ERRORS as exc:
            logger.warning("прямая ссылка вложения не скачана: %s", exc)
            if not file_id:
                return None
    if file_id:
        try:
            token = await get_current_access_token(session)
            if token is None:
                logger.warning("нет OAuth: file id вложения не скачан")
                return None
            return await client.download_file_by_id(file_id=file_id, access_token=token)
        except _FETCH_ERRORS as exc:
            logger.warning("вложение по file id не скачано: %s", exc)
            return None
    return None
