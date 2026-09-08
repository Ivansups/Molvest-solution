"""Тесты канального handoff: черновик после эскалации, сбой generate."""

from unittest.mock import AsyncMock
from uuid import UUID

from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.services import channel_handoff
from app.services.conversation_status import transition_status

_INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


async def _escalated(db_session: AsyncSession) -> Conversation:
    conversation = Conversation(
        installation_id=_INSTALL,
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    transition_status(conversation, ConversationStatus.ESCALATED)
    await db_session.commit()
    return conversation


async def test_fill_escalation_draft_stores_suggestion(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = await _escalated(db_session)
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(return_value="Черновик оператору"),
    )

    draft = await channel_handoff.fill_escalation_draft(
        db_session,
        conversation_id=conversation.id,
        query="как провести документ?",
    )

    assert draft == "Черновик оператору"
    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed is not None
    assert refreshed.status == ConversationStatus.ESCALATED
    assert refreshed.suggested_response == "Черновик оператору"


async def test_fill_escalation_draft_keeps_status_on_generate_error(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = await _escalated(db_session)
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(side_effect=RuntimeError("gigachat down")),
    )

    draft = await channel_handoff.fill_escalation_draft(
        db_session,
        conversation_id=conversation.id,
        query="слабый вопрос",
    )

    assert draft is None
    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed is not None
    assert refreshed.status == ConversationStatus.ESCALATED
    assert refreshed.suggested_response is None
