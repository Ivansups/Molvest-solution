"""REST-клиент Bitrix24: исходящие вызовы методов приложения.

Вся специфика протокола Bitrix живёт здесь (см. AGENTS.md — специфика канала в
`channels/<канал>/`). URL базового вебхука содержит ключ приложения, поэтому
URL в лог никогда не пишется: логируем только имя метода и статус.
"""

import base64
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_REST_TIMEOUT = 30.0


class Bitrix24RestError(Exception):
    """Ошибка вызова REST Bitrix24 (аппликационный ответ об ошибке)."""


def build_rest_client() -> "Bitrix24RestClient":
    """Собирает клиент из `BITRIX_*` env (для тестов подменяется)."""
    return Bitrix24RestClient(
        portal_url=settings.bitrix_portal_url,
        app_user_id=settings.bitrix_app_user_id,
        app_token=settings.bitrix_app_token,
    )


class Bitrix24RestClient:
    """Клиент REST Bitrix24: вебхук (`/rest/{user}/{token}/`) для методов без
    контекста приложения, OAuth (`?auth=`) для `imconnector.*`/`imbot.*` —
    те требуют установленное приложение (см. design.md, D8).

    Не является потокобезопасным, рассчитан на один вызов за время жизни.
    """

    def __init__(
        self,
        *,
        portal_url: str,
        app_user_id: str,
        app_token: str,
    ) -> None:
        self._domain = urlparse(portal_url).netloc
        self._base_url = f"{portal_url.rstrip('/')}/rest/{app_user_id}/{app_token}/"
        self._client = httpx.AsyncClient(timeout=_REST_TIMEOUT)

    async def aclose(self) -> None:
        """Закрывает внутренний HTTP-клиент."""
        await self._client.aclose()

    async def send_message(
        self,
        *,
        connector_id: str,
        chat_id: str,
        text: str,
        access_token: str,
    ) -> dict[str, object]:
        """Отправляет ответ агента в диалог открытой линии через OAuth."""
        return await self._call_oauth(
            "imconnector.send.messages",
            {
                "CONNECTOR": connector_id,
                "LINE": settings.bitrix_line_id,
                "MESSAGES": [{"user": {"id": chat_id}, "message": {"text": text}}],
            },
            access_token=access_token,
        )

    async def download_image(self, url: str) -> str:
        """Скачивает картинку по прямой ссылке и кодирует в base64.

        Хост ссылки обязан совпадать с доменом портала — событие приходит от
        клиента и не должно позволять серверу ходить на произвольные адреса
        (SSRF).
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc != self._domain:
            raise Bitrix24RestError(f"вложение с недопустимого хоста: {url}")
        response = await self._client.get(url, follow_redirects=False)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")

    async def _call(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        """POST в метод приложения по вебхуку. URL с ключом в лог не попадает."""
        return await self._post(f"{self._base_url}{method}", method, payload)

    async def _call_oauth(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        access_token: str,
    ) -> dict[str, object]:
        """POST в метод, требующий контекст приложения. Токен в URL, не в лог."""
        url = f"https://{self._domain}/rest/{method}?auth={access_token}"
        return await self._post(url, method, payload)

    async def _post(
        self,
        url: str,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        logger.info("bitrix rest %s отправка", method)
        try:
            response = await self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("bitrix rest %s сетевой сбой: %s", method, exc)
            raise Bitrix24RestError(f"{method}: {exc}") from exc
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            logger.warning("bitrix rest %s ответ не объект", method)
            raise Bitrix24RestError(f"{method}: ответ не объект")
        if "error" in data:
            detail = data.get("error_description") or data.get("error")
            logger.warning("bitrix rest %s ошибка API: %s", method, detail)
            raise Bitrix24RestError(f"{method}: {detail}")
        return data
