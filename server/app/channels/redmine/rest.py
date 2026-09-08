"""Исходящие заметки в тикет Redmine (REST). Секрет не логируется."""

import asyncio
import logging
import re
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_TICKET_ID_RE = re.compile(r"^\d+$")


class RedmineRestError(Exception):
    """Ошибка исходящего вызова Redmine или SMTP."""


class RedmineClient:
    """PUT /issues/{id}.json с notes либо SMTP, если REST не задан."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http: httpx.AsyncClient | None
        if http is not None:
            self._http = http
        elif self._base_url and self._api_key:
            self._http = httpx.AsyncClient(timeout=_TIMEOUT)
        else:
            self._http = None

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    async def add_note(self, ticket_id: str, text: str) -> None:
        """Пишет заметку в тикет. Ключ API в лог не попадает."""
        safe_id = _safe_ticket_id(ticket_id)
        if self._base_url and self._api_key:
            await self._put_notes(safe_id, text)
            return
        if settings.redmine_smtp_host:
            await self._send_smtp(safe_id, text)
            return
        logger.warning("redmine REST/SMTP не сконфигурирован: ответ не ушёл")
        raise RedmineRestError("нет исходящего транспорта")

    async def _put_notes(self, ticket_id: str, text: str) -> None:
        if self._http is None:
            raise RedmineRestError("нет исходящего транспорта")
        url = f"{self._base_url}/issues/{ticket_id}.json"
        logger.info("redmine rest notes ticket_id=%s", ticket_id)
        try:
            response = await self._http.put(
                url,
                json={"issue": {"notes": text}},
                headers={"X-Redmine-API-Key": self._api_key},
            )
        except httpx.HTTPError as exc:
            logger.warning("redmine rest сетевой сбой: %s", exc)
            raise RedmineRestError(str(exc)) from exc
        if response.status_code >= 400:
            logger.warning("redmine rest status=%s", response.status_code)
            raise RedmineRestError(f"HTTP {response.status_code}")

    async def _send_smtp(self, ticket_id: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = settings.redmine_smtp_from
        message["To"] = settings.redmine_smtp_user
        message["Subject"] = f"Re: [#{ticket_id}]"
        message.set_content(text)
        logger.info("redmine smtp ticket_id=%s", ticket_id)
        try:
            await asyncio.to_thread(self._smtp_send, message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("redmine smtp сбой ticket_id=%s", ticket_id)
            raise RedmineRestError("smtp") from exc

    def _smtp_send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(
            settings.redmine_smtp_host, settings.redmine_smtp_port
        ) as smtp:
            smtp.starttls()
            if settings.redmine_smtp_user:
                smtp.login(settings.redmine_smtp_user, settings.redmine_smtp_password)
            smtp.send_message(message)

    @staticmethod
    def is_configured() -> bool:
        """True, если есть REST или SMTP для исходящего ответа."""
        if settings.redmine_url and settings.redmine_api_key:
            return True
        return bool(settings.redmine_smtp_host)


def _safe_ticket_id(ticket_id: str) -> str:
    """Только цифры — иначе путь REST можно увести с /issues/{id}."""
    if not _TICKET_ID_RE.fullmatch(ticket_id):
        raise RedmineRestError("некорректный ticket_id")
    return ticket_id


def build_redmine_client() -> RedmineClient | None:
    """Клиент или None, если исходящее не настроено."""
    if not RedmineClient.is_configured():
        return None
    return RedmineClient(
        base_url=settings.redmine_url,
        api_key=settings.redmine_api_key,
    )
