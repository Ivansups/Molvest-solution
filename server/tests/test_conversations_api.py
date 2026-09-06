"""Read-only API диалогов этапа 6: список, фильтры, детали и метрики."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message

INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_INSTALL = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


async def _make_conversation(
    db_session: AsyncSession,
    *,
    installation_id: UUID = INSTALL,
    user_id: str = "u1",
    escalated: bool = False,
    response_delay: timedelta = timedelta(seconds=0),
) -> Conversation:
    """Создаёт диалог с user- и assistant/system-сообщением и optional эскалацией."""
    conversation = Conversation(
        installation_id=installation_id,
        user_id=user_id,
        status=ConversationStatus.ESCALATED if escalated else ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()

    started = datetime.now(UTC)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="вопрос",
            created_at=started,
        )
    )
    assistant = Message(
        conversation_id=conversation.id,
        role=MessageRole.SYSTEM if escalated else MessageRole.ASSISTANT,
        content="Передано оператору" if escalated else "ответ",
        confidence=0.4 if escalated else 0.95,
        escalated=escalated,
        sources=[{"doc": "x"}] if not escalated else [],
        created_at=started + response_delay,
    )
    db_session.add(assistant)
    await db_session.flush()

    if escalated:
        db_session.add(
            Escalation(
                conversation_id=conversation.id,
                message_id=assistant.id,
                reason="Низкая уверенность",
                escalated_to="operator",
            )
        )
    await db_session.commit()
    return conversation


async def test_list_conversations_paginated(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _make_conversation(db_session, user_id="one")
    await _make_conversation(db_session, user_id="two")

    response = await api_client.get(
        "/api/conversations",
        params={"installation_id": str(INSTALL), "page": 1, "page_size": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    # пагинация: вторая страница отдаёт второй диалог
    second = await api_client.get(
        "/api/conversations",
        params={"installation_id": str(INSTALL), "page": 2, "page_size": 1},
    )
    assert len(second.json()["items"]) == 1


async def test_list_filters_by_status_escalated(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _make_conversation(db_session, user_id="open-user", escalated=False)
    await _make_conversation(db_session, user_id="esc-user", escalated=True)

    response = await api_client.get(
        "/api/conversations",
        params={"installation_id": str(INSTALL), "status": "escalated"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["status"] == "escalated"
    assert item["user_id"] == "esc-user"


async def test_list_filters_by_user_id(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _make_conversation(db_session, user_id="alice")
    await _make_conversation(db_session, user_id="bob")

    response = await api_client.get(
        "/api/conversations",
        params={"installation_id": str(INSTALL), "user_id": "alice"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["user_id"] == "alice"


async def test_list_scoped_to_installation(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _make_conversation(db_session, installation_id=INSTALL)
    await _make_conversation(db_session, installation_id=OTHER_INSTALL)

    response = await api_client.get(
        "/api/conversations",
        params={"installation_id": str(INSTALL)},
    )
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["installation_id"] == str(INSTALL)


async def test_get_detail_returns_messages_and_escalations(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _make_conversation(db_session, user_id="detail", escalated=True)

    response = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "escalated"
    roles = {m["role"] for m in body["messages"]}
    assert roles == {"user", "system"}
    assert len(body["escalations"]) == 1
    escalation = body["escalations"][0]
    assert escalation["escalated_to"] == "operator"
    # message_id эскалации указывает на сохранённое system-сообщение
    system = next(m for m in body["messages"] if m["role"] == "system")
    assert escalation["message_id"] == system["id"]
    assert body["suggested_response"] is None


async def test_get_detail_unknown_id_returns_404(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(
        f"/api/conversations/{uuid4()}",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 404


async def test_get_detail_scoped_to_installation_returns_404(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    conv = await _make_conversation(db_session, installation_id=OTHER_INSTALL)

    response = await api_client.get(
        f"/api/conversations/{conv.id}",
        params={"installation_id": str(INSTALL)},
    )
    assert response.status_code == 404


async def test_metrics_returns_auto_answer_percent_and_count(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1 автоответ (assistant, не escalated) + 1 эскалированный (system, escalated)
    await _make_conversation(
        db_session, user_id="auto", escalated=False, response_delay=timedelta(seconds=2)
    )
    await _make_conversation(
        db_session, user_id="esc", escalated=True, response_delay=timedelta(seconds=4)
    )
    # шум в другой установке не должен попадать в метрики INSTALL
    await _make_conversation(
        db_session,
        installation_id=OTHER_INSTALL,
        user_id="other",
        escalated=True,
        response_delay=timedelta(seconds=100),
    )

    response = await api_client.get(
        "/api/metrics", params={"installation_id": str(INSTALL)}
    )
    assert response.status_code == 200
    body = response.json()
    # 2 ассистентских/system ответа всего, 1 из них эскалирован → 50% автоответов
    assert body["auto_answer_percent"] == 50.0
    assert body["escalation_count"] == 1
    # среднее (2с + 4с) / 2
    assert body["avg_response_time_seconds"] == 3.0


async def test_metrics_empty_installation_is_zero(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(
        "/api/metrics", params={"installation_id": str(INSTALL)}
    )
    body = response.json()
    assert body["auto_answer_percent"] == 0.0
    assert body["escalation_count"] == 0
    assert body["avg_response_time_seconds"] == 0.0
