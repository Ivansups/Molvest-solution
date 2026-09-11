"""Redmine HelpDesk: вебхук, маппинг, дубль, эскалация, исходящая заметка."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_graph
from app.agent.state import RetrievedChunk
from app.channels.redmine.imap import (
    ParsedMail,
    ingest_email_event,
    parse_rfc822,
    poll_mailbox,
    ticket_id_from_subject,
)
from app.channels.redmine.rest import RedmineClient, RedmineRestError
from app.channels.redmine.schemas import RedmineEvent
from app.core.config import Settings, settings
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.services import runtime_settings

PATH = "/webhook/redmine"
TOKEN = "redmine-secret"


class _FakeRedmineClient:
    def __init__(self) -> None:
        self.add_note = AsyncMock(return_value=None)
        self.aclose = AsyncMock(return_value=None)


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


@pytest.fixture(autouse=True)
def _mock_channel_draft(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.channel_handoff.generate_draft",
        AsyncMock(return_value="Черновик оператору"),
    )


@pytest.fixture
def fake_redmine(monkeypatch: MonkeyPatch) -> _FakeRedmineClient:
    client = _FakeRedmineClient()
    monkeypatch.setattr("app.services.redmine.build_redmine_client", lambda: client)
    return client


@pytest.fixture
def cache_mocks(monkeypatch: MonkeyPatch) -> None:
    import app.agent.graph as graph_mod

    monkeypatch.setattr(graph_mod, "get_kb_version", AsyncMock(return_value=3))
    monkeypatch.setattr(graph_mod, "get_cached_answer", AsyncMock(return_value=None))
    monkeypatch.setattr(graph_mod, "set_cached_answer", AsyncMock())


def _payload(
    *,
    ticket_id: str = "12",
    message_id: str = "m-1",
    sender: str = "user",
    text: str = "как провести документ?",
) -> dict[str, str]:
    return {
        "ticket_id": ticket_id,
        "message_id": message_id,
        "sender": sender,
        "text": text,
        "workspace_id": "redmine",
    }


def _patch_auto_graph(
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    *,
    weak: bool = False,
    answer: str = "Ответ в тикет",
) -> None:
    import app.services.agent as agent_service

    score = 0.3 if weak else 0.9

    async def hit(_state: object) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                document_id=str(uuid4()),
                title="Инструкция",
                chunk_text="провести",
                score=score,
            )
        ]

    llm_mock.generate = AsyncMock(return_value=answer)  # type: ignore[attr-defined]
    graph = build_graph(llm_mock, app_settings, retriever=hit)  # type: ignore[arg-type]
    monkeypatch.setattr(agent_service, "get_graph", lambda: graph)


async def test_invalid_token_is_403(
    api_client: AsyncClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 403


async def test_malformed_body_is_422(api_client: AsyncClient) -> None:
    response = await api_client.post(PATH, json={"ticket_id": "1"})
    assert response.status_code == 422


async def test_first_ticket_creates_conversation_and_sends_note(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["reply"] == "Ответ в тикет"
    assert body["delivered"] is True
    fake_redmine.add_note.assert_awaited_once()
    mapping = (
        await db_session.scalars(
            select(ChannelThread).where(ChannelThread.channel == "redmine")
        )
    ).first()
    assert mapping is not None
    assert mapping.thread_id == "12"


async def test_same_ticket_continues_conversation(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    first = await api_client.post(PATH, json=_payload(message_id="a"))
    second = await api_client.post(PATH, json=_payload(message_id="b", text="второй"))
    assert first.json()["conversation_id"] == second.json()["conversation_id"]
    mappings = list(
        (
            await db_session.scalars(
                select(ChannelThread).where(ChannelThread.thread_id == "12")
            )
        ).all()
    )
    assert len(mappings) == 1


async def test_duplicate_message_twice(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    first = await api_client.post(PATH, json=_payload())
    second = await api_client.post(PATH, json=_payload())
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    assert fake_redmine.add_note.await_count == 1


async def test_escalation_does_not_note_guest(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, weak=True)
    response = await api_client.post(PATH, json=_payload(text="абракадабра"))
    assert response.json()["escalated"] is True
    fake_redmine.add_note.assert_not_awaited()
    conversation = await db_session.get(
        Conversation, UUID(response.json()["conversation_id"])
    )
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Черновик оператору"


async def test_draft_followup_after_escalation_does_not_note(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, weak=True)
    first = await api_client.post(PATH, json=_payload(message_id="esc-1"))
    assert first.json()["escalated"] is True
    fake_redmine.add_note.assert_not_awaited()
    second = await api_client.post(
        PATH, json=_payload(message_id="esc-2", text="ещё раз")
    )
    assert second.status_code == 200
    fake_redmine.add_note.assert_not_awaited()
    conversation = await db_session.get(
        Conversation, UUID(first.json()["conversation_id"])
    )
    assert conversation is not None
    assert conversation.suggested_response == "Черновик оператору"


async def test_operator_does_not_run_graph(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    fake_redmine: _FakeRedmineClient,
) -> None:
    import app.services.agent as agent_service

    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: (_ for _ in ()).throw(AssertionError("граф")),
    )
    response = await api_client.post(
        PATH, json=_payload(sender="operator", text="сейчас посмотрю")
    )
    assert response.status_code == 200
    fake_redmine.add_note.assert_not_awaited()
    operators = list(
        (
            await db_session.scalars(
                select(Message).where(Message.role == MessageRole.OPERATOR)
            )
        ).all()
    )
    assert len(operators) == 1


async def test_secrets_not_in_redmine_response(
    api_client: AsyncClient,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "redmine_api_key", "super-redmine-key")
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    response = await api_client.post(PATH, json=_payload())
    assert "super-redmine-key" not in response.text
    for record in caplog.records:
        assert "super-redmine-key" not in record.message


def test_ticket_id_from_subject() -> None:
    assert ticket_id_from_subject("[#42] ошибка 1С") == "42"
    assert ticket_id_from_subject("без номера") is None


async def test_ingest_email_calls_service_once(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)

    class _SessionCM:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("app.channels.redmine.imap.SessionLocal", lambda: _SessionCM())
    await ingest_email_event(ticket_id="9", message_id="mail-1", text="как провести?")
    await ingest_email_event(ticket_id="9", message_id="mail-1", text="как провести?")
    count = await db_session.scalar(
        select(func.count())
        .select_from(ChannelThread)
        .where(ChannelThread.channel == "redmine")
    )
    assert count == 1
    fake_redmine.add_note.assert_awaited_once()


async def test_empty_imap_host_does_not_require_poller() -> None:
    assert settings.redmine_imap_host == ""


def test_ticket_id_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError):
        RedmineEvent(
            ticket_id="../1",
            message_id="m",
            sender="user",
            text="x",
        )


async def test_put_notes_rejects_non_numeric_ticket_id() -> None:
    client = RedmineClient(base_url="https://redmine.example", api_key="k")
    with pytest.raises(RedmineRestError, match="ticket_id"):
        await client.add_note("../projects", "note")
    await client.aclose()


async def test_smtp_failure_is_redmine_error(
    monkeypatch: MonkeyPatch,
) -> None:
    import smtplib

    monkeypatch.setattr(settings, "redmine_smtp_host", "smtp.example")
    monkeypatch.setattr(settings, "redmine_smtp_from", "a@b.c")
    monkeypatch.setattr(settings, "redmine_smtp_user", "a@b.c")
    client = RedmineClient(base_url="", api_key="")
    monkeypatch.setattr(
        client,
        "_smtp_send",
        MagicMock(side_effect=smtplib.SMTPException("down")),
    )
    with pytest.raises(RedmineRestError, match="smtp"):
        await client.add_note("12", "hi")
    await client.aclose()


def test_parse_rfc822_reads_ticket_and_body() -> None:
    raw = (
        b"From: user@example.com\r\n"
        b"Subject: [#42] error\r\n"
        b"Message-ID: <mail-42@example.com>\r\n"
        b"\r\n"
        b"how to post a document?\r\n"
    )
    parsed = parse_rfc822(raw)
    assert parsed is not None
    assert parsed.ticket_id == "42"
    assert parsed.message_id == "<mail-42@example.com>"
    assert "document" in parsed.text


def test_parse_rfc822_without_ticket_is_none() -> None:
    raw = b"Subject: no ticket\r\n\r\nhello\r\n"
    assert parse_rfc822(raw) is None


async def test_poll_mailbox_ingests_each_message(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_ingest(**kwargs: object) -> None:
        calls.append(str(kwargs["message_id"]))

    monkeypatch.setattr(
        "app.channels.redmine.imap.fetch_unseen_messages",
        lambda: [
            ParsedMail("9", "m1", "первый"),
            ParsedMail("9", "m2", "второй"),
        ],
    )
    monkeypatch.setattr(
        "app.channels.redmine.imap.ingest_email_event",
        fake_ingest,
    )
    count = await poll_mailbox()
    assert count == 2
    assert calls == ["m1", "m2"]


async def test_agent_mode_high_score_does_not_note_guest(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings, answer="Ответ в тикет")
    response = await api_client.post(PATH, json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["escalated"] is True
    fake_redmine.add_note.assert_not_awaited()
    conversation = await db_session.get(Conversation, UUID(body["conversation_id"]))
    assert conversation is not None
    assert conversation.status == ConversationStatus.ESCALATED
    assert conversation.suggested_response == "Ответ в тикет"


async def test_agent_mode_duplicate_message_twice(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
    llm_mock: object,
    app_settings: Settings,
    cache_mocks: object,
    fake_redmine: _FakeRedmineClient,
) -> None:
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    _patch_auto_graph(monkeypatch, llm_mock, app_settings)
    first = await api_client.post(PATH, json=_payload())
    second = await api_client.post(PATH, json=_payload())
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    fake_redmine.add_note.assert_not_awaited()
