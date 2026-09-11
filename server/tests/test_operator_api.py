"""API оператора: ответ, resolve, suggest."""

from unittest.mock import AsyncMock, patch
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


def _resolve_payload(
    *,
    confirmed: bool = True,
    comment: str | None = None,
    include_confirmed: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {"installation_id": str(INSTALL)}
    if include_confirmed:
        payload["confirmed"] = confirmed
    if comment is not None:
        payload["comment"] = comment
    return payload


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
        json=_resolve_payload(),
    )
    assert first.status_code == 200
    assert first.json()["status"] == "resolved"
    second = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(),
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
    assert body["resolve_comment"] is None
    assert body["resolve_confirmed_at"] is not None


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
        json=_resolve_payload(),
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
        json=_resolve_payload(),
    )
    assert response.status_code == 409


async def test_resolve_without_confirmed_returns_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(include_confirmed=False),
    )
    assert response.status_code == 422
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    body = detail.json()
    assert body["status"] == "escalated"
    assert body["resolve_comment"] is None
    assert body["resolve_confirmed_at"] is None


async def test_resolve_confirmed_false_returns_422(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(confirmed=False),
    )
    assert response.status_code == 422
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    assert detail.json()["status"] == "escalated"


async def test_resolve_stores_comment_on_get(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(comment="готово"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["resolve_comment"] == "готово"
    assert response.json()["resolve_confirmed_at"] is not None
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    body = detail.json()
    assert body["resolve_comment"] == "готово"
    assert body["resolve_confirmed_at"] is not None
    assert body["resolve_confirmed_at"].endswith(("Z", "+00:00"))


async def test_resolve_comment_not_in_guest_payloads(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.channels.bitrix.rest import Bitrix24RestClient
    from app.channels.redmine.rest import RedmineClient
    from app.schemas.chat import ChatResponse

    conv = await _escalated_conversation(db_session)
    comment = "готово-секрет"
    with (
        patch.object(
            Bitrix24RestClient, "send_message", new_callable=AsyncMock
        ) as bitrix_ol,
        patch.object(
            Bitrix24RestClient, "send_bot_message", new_callable=AsyncMock
        ) as bitrix_bot,
        patch.object(RedmineClient, "add_note", new_callable=AsyncMock) as redmine,
    ):
        response = await api_client.post(
            f"/api/conversations/{conv.id}/resolve",
            json=_resolve_payload(comment=comment),
        )
    assert response.status_code == 200
    bitrix_ol.assert_not_awaited()
    bitrix_bot.assert_not_awaited()
    redmine.assert_not_awaited()
    assert "resolve_comment" not in ChatResponse.model_fields
    detail = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    body = detail.json()
    assert body["resolve_comment"] == comment
    for message in body["messages"]:
        assert comment not in message["content"]


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


async def test_resolve_other_installation_404(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    response = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json={"installation_id": str(OTHER), "confirmed": True},
    )
    assert response.status_code == 404


async def test_resolve_already_resolved_confirmed_false_returns_200(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _escalated_conversation(db_session)
    first = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(),
    )
    assert first.status_code == 200
    second = await api_client.post(
        f"/api/conversations/{conv.id}/resolve",
        json=_resolve_payload(confirmed=False),
    )
    assert second.status_code == 200
    assert second.json()["status"] == "resolved"
