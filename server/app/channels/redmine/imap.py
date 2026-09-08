"""Опциональный IMAP: UNSEEN → тот же сервис, что и вебхук."""

import asyncio
import email
import imaplib
import logging
import re
from email.message import Message
from typing import Literal, NamedTuple

from app.channels.redmine.schemas import RedmineEvent
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.redmine import process_redmine_event

logger = logging.getLogger(__name__)

_TICKET_RE = re.compile(r"#(\d+)")
_POLL_SECONDS = 60


class ParsedMail(NamedTuple):
    """Письмо, которое можно положить в process_redmine_event."""

    ticket_id: str
    message_id: str
    text: str


def ticket_id_from_subject(subject: str) -> str | None:
    """Номер тикета Redmine из темы письма (`[#123]`)."""
    match = _TICKET_RE.search(subject)
    return match.group(1) if match else None


def parse_rfc822(raw: bytes) -> ParsedMail | None:
    """Разбирает сырое письмо. Без номера тикета — None (не ingest)."""
    message = email.message_from_bytes(raw)
    ticket_id = ticket_id_from_subject(_header(message, "Subject"))
    if ticket_id is None:
        return None
    message_id = _header(message, "Message-ID") or f"imap-{ticket_id}"
    return ParsedMail(
        ticket_id=ticket_id,
        message_id=message_id,
        text=_plain_text(message),
    )


async def ingest_email_event(
    *,
    ticket_id: str,
    message_id: str,
    text: str,
    sender: Literal["user", "operator"] = "user",
) -> None:
    """Кладёт письмо в тот же сервис, что и вебхук."""
    event = RedmineEvent(
        ticket_id=ticket_id,
        message_id=message_id,
        sender=sender,
        text=text,
    )
    async with SessionLocal() as session:
        await process_redmine_event(session, event)


async def poll_mailbox() -> int:
    """Один проход: UNSEEN с ящика → ingest. Возвращает число писем."""
    items = await asyncio.to_thread(fetch_unseen_messages)
    for item in items:
        await ingest_email_event(
            ticket_id=item.ticket_id,
            message_id=item.message_id,
            text=item.text,
        )
    return len(items)


async def run_imap_poller() -> None:
    """Крутится, пока задан REDMINE_IMAP_HOST."""
    if not settings.redmine_imap_host:
        return
    logger.info("redmine imap поллер запущен host=%s", settings.redmine_imap_host)
    while True:
        try:
            await poll_mailbox()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("redmine imap сбой: %s", exc)
        await asyncio.sleep(_POLL_SECONDS)


def fetch_unseen_messages() -> list[ParsedMail]:
    """Читает UNSEEN и помечает прочитанными. Пароль в лог не пишет."""
    host = settings.redmine_imap_host
    if not host or not settings.redmine_imap_user:
        return []
    mailbox = imaplib.IMAP4_SSL(host, settings.redmine_imap_port)
    try:
        mailbox.login(settings.redmine_imap_user, settings.redmine_imap_password)
        mailbox.select("INBOX")
        status, data = mailbox.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []
        result: list[ParsedMail] = []
        for raw_num in data[0].split():
            num = raw_num.decode() if isinstance(raw_num, bytes) else str(raw_num)
            parsed = _fetch_one(mailbox, num)
            mailbox.store(num, "+FLAGS", r"\Seen")
            if parsed is not None:
                result.append(parsed)
        return result
    finally:
        try:
            mailbox.logout()
        except OSError:
            pass


def _fetch_one(mailbox: imaplib.IMAP4, num: str) -> ParsedMail | None:
    status, fetched = mailbox.fetch(num, "(RFC822)")
    if status != "OK" or not fetched:
        return None
    first = fetched[0]
    if not isinstance(first, tuple) or len(first) < 2:
        return None
    raw = first[1]
    if not isinstance(raw, bytes):
        return None
    return parse_rfc822(raw)


def _header(message: Message, name: str) -> str:
    value = message.get(name)
    return str(value).strip() if value else ""


def _plain_text(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                return _decode_part(part)
        return ""
    return _decode_part(message)


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace").strip()
    if isinstance(payload, str):
        return payload.strip()
    return ""
