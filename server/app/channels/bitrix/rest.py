"""REST-клиент Bitrix24: исходящие вызовы методов приложения.

Вся специфика протокола Bitrix живёт здесь (см. AGENTS.md — специфика канала в
`channels/<канал>/`). URL базового вебхука содержит ключ приложения, поэтому
URL в лог никогда не пишется: логируем только имя метода и статус.
"""

import base64
import logging
from typing import Any

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
    """Единый клиент REST-вебхука Bitrix24 (`/rest/{user}/{token}/`).

    Не является потокобезопасным, рассчитан на один вызов за время жизни.
    """

    def __init__(
        self,
        *,
        portal_url: str,
        app_user_id: str,
        app_token: str,
    ) -> None:
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
    ) -> dict[str, object]:
        """Отправляет сообщение пользователя приложения в диалог открытой линии."""
        return await self._call(
            "imconnector.send.messages",
            {
                "connector_id": connector_id,
                "chat_id": chat_id,
                "messages": [{"message": text}],
            },
        )

    async def download_image(self, url: str) -> str:
        """Скачивает картинку по прямой ссылке и кодирует в base64."""
        response = await self._client.get(url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")

    async def _call(
        self,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        """POST в метод приложения. URL с ключом в лог не попадает."""
        logger.info("bitrix rest %s отправка", method)
        try:
            response = await self._client.post(
                f"{self._base_url}{method}",
                json=payload,
            )
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
