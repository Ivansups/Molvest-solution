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


def _http_fail_label(exc: httpx.HTTPError) -> str:
    """Код/тип ошибки без URL — в URL OAuth и file token."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return f"HTTP {status}"
    return type(exc).__name__


class Bitrix24RestError(Exception):
    """Ошибка вызова REST Bitrix24 (аппликационный ответ об ошибке)."""


def build_rest_client() -> "Bitrix24RestClient":
    """Собирает клиент из `BITRIX_*` env (для тестов подменяется)."""
    return Bitrix24RestClient(
        portal_url=settings.bitrix_portal_url,
        app_user_id=settings.bitrix_app_user_id,
        app_token=settings.bitrix_app_token,
    )


def maybe_build_rest_client() -> "Bitrix24RestClient | None":
    """Клиент при полной конфигурации портала, иначе None."""
    if not (
        settings.bitrix_portal_url
        and settings.bitrix_app_user_id
        and settings.bitrix_app_token
    ):
        return None
    return build_rest_client()


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

    async def send_bot_message(
        self,
        *,
        bot_id: str,
        dialog_id: str,
        text: str,
        access_token: str,
    ) -> dict[str, object]:
        """Отправляет ответ бота в диалог клиента (`imbot.message.add`)."""
        return await self._call_oauth(
            "imbot.message.add",
            {"BOT_ID": bot_id, "DIALOG_ID": dialog_id, "MESSAGE": text},
            access_token=access_token,
        )

    async def list_bots(self, access_token: str) -> dict[str, object]:
        """Список ботов приложения (`imbot.bot.list`)."""
        return await self._call_oauth("imbot.bot.list", {}, access_token=access_token)

    async def register_openlines_bot(
        self,
        *,
        code: str,
        handler_url: str,
        name: str,
        access_token: str,
    ) -> dict[str, object]:
        """Регистрирует бота открытой линии (`imbot.register`)."""
        return await self._call_oauth(
            "imbot.register",
            {
                "CODE": code,
                "TYPE": "O",
                "OPENLINE": "Y",
                "EVENT_MESSAGE_ADD": handler_url,
                "EVENT_WELCOME_MESSAGE": handler_url,
                "EVENT_BOT_DELETE": handler_url,
                "PROPERTIES": {"NAME": name},
            },
            access_token=access_token,
        )

    async def send_operator_note(
        self,
        *,
        dialog_id: str,
        text: str,
        access_token: str,
    ) -> dict[str, object]:
        """Черновик оператору: личное уведомление, не реплика гостю.

        Метод `im.notify` на пользователя приложения (`BITRIX_APP_USER_ID`).
        Клиент онлайн-чата это не видит. Спайк на живом портале — design.md D2.
        """
        to = settings.bitrix_app_user_id
        message = f"Черновик (диалог {dialog_id}):\n{text}"
        return await self._call_oauth(
            "im.notify",
            {"to": to, "message": message, "type": "SYSTEM"},
            access_token=access_token,
        )

    async def download_file_by_id(
        self,
        *,
        file_id: str,
        access_token: str,
    ) -> str:
        """Скачивает файл диска по id (OAuth) и кодирует в base64."""
        data = await self._call_oauth(
            "disk.file.get",
            {"id": file_id},
            access_token=access_token,
        )
        result = data.get("result")
        if not isinstance(result, dict):
            raise Bitrix24RestError("disk.file.get: нет объекта result")
        url = result.get("DOWNLOAD_URL") or result.get("downloadUrl")
        if not isinstance(url, str) or not url:
            raise Bitrix24RestError("disk.file.get: нет DOWNLOAD_URL")
        return await self.download_image(url)

    async def download_image(self, url: str) -> str:
        """Скачивает картинку по прямой ссылке и кодирует в base64.

        Хост ссылки обязан совпадать с доменом портала — событие приходит от
        клиента и не должно позволять серверу ходить на произвольные адреса
        (SSRF).
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc != self._domain:
            raise Bitrix24RestError(f"вложение с недопустимого хоста: {parsed.netloc}")
        try:
            response = await self._client.get(url, follow_redirects=False)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            label = _http_fail_label(exc)
            logger.warning(
                "bitrix rest download сбой host=%s %s",
                parsed.netloc,
                label,
            )
            raise Bitrix24RestError(f"скачивание вложения: {label}") from exc
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
            response.raise_for_status()
        except httpx.HTTPError as exc:
            label = _http_fail_label(exc)
            logger.warning("bitrix rest %s сбой %s", method, label)
            raise Bitrix24RestError(f"{method}: {label}") from exc
        data = response.json()
        if not isinstance(data, dict):
            logger.warning("bitrix rest %s ответ не объект", method)
            raise Bitrix24RestError(f"{method}: ответ не объект")
        if "error" in data:
            detail = data.get("error_description") or data.get("error")
            logger.warning("bitrix rest %s ошибка API: %s", method, detail)
            raise Bitrix24RestError(f"{method}: {detail}")
        return data
