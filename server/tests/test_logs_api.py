"""Админский журнал: составная витрина из эскалаций, закрытий и документов."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import ConversationStatus, DocumentStatus, FileType, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message

INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_INSTALL = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


async def _escalated_conversation(
    db_session: AsyncSession,
    *,
    installation_id: UUID = INSTALL,
    occurred_at: datetime = NOW,
    reason: str = "Низкая уверенность",
    resolved_at: datetime | None = None,
    resolve_comment: str | None = None,
) -> Conversation:
    status = (
        ConversationStatus.RESOLVED
        if resolved_at is not None
        else ConversationStatus.ESCALATED
    )
    conversation = Conversation(
        installation_id=installation_id,
        user_id="u1",
        status=status,
        resolve_comment=resolve_comment,
        resolve_confirmed_at=resolved_at,
    )
    db_session.add(conversation)
    await db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.SYSTEM,
        content="Передано оператору",
        escalated=True,
        created_at=occurred_at,
    )
    db_session.add(message)
    await db_session.flush()
    db_session.add(
        Escalation(
            conversation_id=conversation.id,
            message_id=message.id,
            reason=reason,
            escalated_to="operator",
            resolved_at=resolved_at,
        )
    )
    await db_session.commit()
    return conversation


async def _document(
    db_session: AsyncSession,
    *,
    installation_id: UUID = INSTALL,
    status: DocumentStatus,
    title: str,
    indexed_at: datetime,
    indexing_error: str | None = None,
) -> Document:
    metadata: dict[str, object] = {}
    if indexing_error is not None:
        metadata["indexing_error"] = indexing_error
    document = Document(
        installation_id=installation_id,
        title=title,
        file_name=f"{title}.md",
        file_type=FileType.MD,
        status=status,
        indexed_at=indexed_at,
        extra_metadata=metadata,
    )
    db_session.add(document)
    await db_session.commit()
    return document


async def test_logs_empty_without_events(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 50


async def test_logs_returns_events_newest_first(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _escalated_conversation(
        db_session,
        occurred_at=NOW - timedelta(hours=3),
        reason="Низкая уверенность",
    )
    await _escalated_conversation(
        db_session,
        occurred_at=NOW - timedelta(hours=2),
        resolved_at=NOW - timedelta(hours=1),
        resolve_comment="Исправлено в 1С",
    )
    failed = await _document(
        db_session,
        status=DocumentStatus.FAILED,
        title="Касса",
        indexed_at=NOW - timedelta(minutes=30),
        indexing_error="файл пуст",
    )
    indexed = await _document(
        db_session,
        status=DocumentStatus.INDEXED,
        title="Регламент",
        indexed_at=NOW,
    )

    response = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    types = [item["event_type"] for item in body["items"]]
    assert types == [
        "document_indexed",
        "document_failed",
        "conversation_resolved",
        "escalation",
        "escalation",
    ]
    assert body["items"][0]["document_id"] == str(indexed.id)
    assert body["items"][0]["occurred_at"].startswith("2026-09-13T12:00:00")
    assert "Регламент" in body["items"][0]["message"]
    assert body["items"][1]["document_id"] == str(failed.id)
    assert body["items"][1]["message"] == "файл пуст"
    assert body["items"][2]["message"] == "Исправлено в 1С"
    assert body["items"][3]["conversation_id"] is not None
    assert body["items"][4]["message"] == "Низкая уверенность"


async def test_logs_filter_by_event_type(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _escalated_conversation(db_session)
    await _document(
        db_session,
        status=DocumentStatus.INDEXED,
        title="Регламент",
        indexed_at=NOW,
    )

    response = await api_client.get(
        "/api/logs",
        params={
            "installation_id": str(INSTALL),
            "event_type": "document_indexed",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "document_indexed"
    assert body["items"][0]["conversation_id"] is None


async def test_logs_excludes_other_installation(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _escalated_conversation(db_session, installation_id=OTHER_INSTALL)
    await _document(
        db_session,
        installation_id=OTHER_INSTALL,
        status=DocumentStatus.FAILED,
        title="Чужой",
        indexed_at=NOW,
        indexing_error="ошибка",
    )

    response = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_logs_date_range_excludes_old(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _escalated_conversation(
        db_session,
        occurred_at=NOW - timedelta(days=5),
        reason="старая",
    )
    await _escalated_conversation(
        db_session,
        occurred_at=NOW,
        reason="свежая",
    )

    response = await api_client.get(
        "/api/logs",
        params={
            "installation_id": str(INSTALL),
            "date_from": (NOW - timedelta(hours=1)).isoformat(),
            "date_to": (NOW + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["message"] == "свежая"


async def test_logs_pagination(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _escalated_conversation(
        db_session, occurred_at=NOW - timedelta(hours=1), reason="раньше"
    )
    await _escalated_conversation(db_session, occurred_at=NOW, reason="позже")

    first = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL), "page": 1, "page_size": 1},
    )
    second = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL), "page": 2, "page_size": 1},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["total"] == 2
    assert first.json()["items"][0]["message"] == "позже"
    assert second.json()["items"][0]["message"] == "раньше"


async def test_logs_requires_installation_id(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/logs")
    assert response.status_code == 422


async def test_logs_rejects_unknown_event_type(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/api/logs",
        params={"installation_id": str(INSTALL), "event_type": "grafana"},
    )
    assert response.status_code == 422
