"""API оператора: ответ, resolve, suggest."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message

INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def _escalated_conversation(
    db_session: AsyncSession,
    *,
    installation_id: UUID = INSTALL,
) -> Conversation:
    conversation = Conversation(
        installation_id=installation_id,
        user_id="guest",
        status=ConversationStatus.ESCALATED,
    )
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="как провести документ",
        )
    )
    system = Message(
        conversation_id=conversation.id,
        role=MessageRole.SYSTEM,
        content="Вопрос передан оператору техподдержки.",
        escalated=True,
    )
    db_session.add(system)
    await db_session.flush()
    db_session.add(
        Escalation(
            conversation_id=conversation.id,
            message_id=system.id,
            reason="Низкая уверенность",
            escalated_to="operator",
        )
    )
    await db_session.commit()
    return conversation


def _mock_suggest(monkeypatch: MonkeyPatch, answer: str) -> None:
    import app.services.draft as draft_service
    from app.agent.state import RetrievedChunk

    monkeypatch.setattr(
        draft_service,
        "make_retriever",
        lambda llm, cfg: AsyncMock(
            return_value=[
                RetrievedChunk(
                    document_id=str(uuid4()),
                    title="Инструкция",
                    chunk_text="провести",
                    score=0.9,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        draft_service,
        "generate",
        AsyncMock(return_value={"answer": answer, "confidence": 0.9}),
    )


async def test_operator_reply_stores_message(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/messages",
        json={"installation_id": str(INSTALL), "text": "Нажмите Провести"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "operator"
    assert body["content"] == "Нажмите Провести"
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    assert detail.json()["suggested_response"] is None
    assert detail.json()["status"] == "escalated"


async def test_operator_reply_rejected_unless_escalated(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conversation = Conversation(
        installation_id=INSTALL,
        user_id="guest",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.commit()
    response = await api_client.post(
        f"/api/conversations/{conversation.id}/messages",
        json={"installation_id": str(INSTALL), "text": "нет"},
    )
    assert response.status_code == 409


async def test_operator_reply_other_installation_404(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/messages",
        json={"installation_id": str(OTHER), "text": "нет"},
    )
    assert response.status_code == 404


async def test_resolve_closes_and_is_idempotent(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    first = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json={"installation_id": str(INSTALL)},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "resolved"
    second = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json={"installation_id": str(INSTALL)},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "resolved"
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    body = detail.json()
    assert body["suggested_response"] is None
    assert body["escalations"][0]["resolved_at"] is not None


async def test_suggest_writes_draft_only(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conv = await _escalated_conversation(db_session)
    _mock_suggest(monkeypatch, "Черновик агента")
    before = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    message_count = len(before.json()["messages"])
    response = await api_client.post(
        f"/api/conversations/{conv.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggested_response"] == "Черновик агента"
    assert body["status"] == "escalated"
    assert len(body["messages"]) == message_count


async def test_suggest_rejected_on_open(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conversation = Conversation(
        installation_id=INSTALL,
        user_id="guest",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.commit()
    response = await api_client.post(
        f"/api/conversations/{conversation.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 409


async def test_suggest_twice_overwrites_draft(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conv = await _escalated_conversation(db_session)
    _mock_suggest(monkeypatch, "первый")
    first = await api_client.post(
        f"/api/conversations/{conv.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    assert first.json()["suggested_response"] == "первый"
    _mock_suggest(monkeypatch, "второй")
    second = await api_client.post(
        f"/api/conversations/{conv.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    body = second.json()
    assert body["suggested_response"] == "второй"
    assert body["status"] == "escalated"
    assert len(body["messages"]) == len(first.json()["messages"])


async def test_reply_and_suggest_rejected_on_resolved(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conv = await _escalated_conversation(db_session)
    closed = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json={"installation_id": str(INSTALL)},
    )
    assert closed.status_code == 200
    reply = await api_client.post(
        f"/api/conversations/{conv.id}/messages",
        json={"installation_id": str(INSTALL), "text": "поздно"},
    )
    assert reply.status_code == 409
    _mock_suggest(monkeypatch, "не должен")
    suggest = await api_client.post(
        f"/api/conversations/{conv.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    assert suggest.status_code == 409
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    assert detail.json()["suggested_response"] is None
    roles = {item["role"] for item in detail.json()["messages"]}
    assert "operator" not in roles


async def test_suggest_without_guest_message_409(
    api_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = Conversation(
        installation_id=INSTALL,
        user_id="guest",
        status=ConversationStatus.ESCALATED,
    )
    db_session.add(conversation)
    await db_session.commit()
    generate = AsyncMock(return_value={"answer": "нет"})
    import app.services.draft as draft_service

    monkeypatch.setattr(draft_service, "generate", generate)
    response = await api_client.post(
        f"/api/conversations/{conversation.id}/suggest",
        json={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 409
    generate.assert_not_called()


async def test_resolve_rejected_on_open(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conversation = Conversation(
        installation_id=INSTALL,
        user_id="guest",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.commit()
    response = await api_client.post(
        f"/api/conversations/{conversation.id}/resolve",
        json={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 409


async def test_suggest_other_installation_404(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/suggest",
        json={"installation_id": str(OTHER)},
    )
    assert response.status_code == 404
