"""Тесты канального handoff: черновик после эскалации, сбой generate."""

from collections.abc import Iterator
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pytest import MonkeyPatch
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.escalation import Escalation
from app.models.message import Message
from app.services import channel_handoff, runtime_settings
from app.services.conversation_status import transition_status
from app.services.conversations import GUEST_ESCALATION_TEXT

_INSTALL = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture(autouse=True)
def _reset_runtime_settings() -> Iterator[None]:
    runtime_settings.reset_effective_settings()
    yield
    runtime_settings.reset_effective_settings()


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


async def test_fill_escalation_draft_skips_generate_if_already_filled(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = await _escalated(db_session)
    conversation.suggested_response = "Уже заполнен"
    await db_session.commit()
    generate_draft = AsyncMock(return_value="не должен")
    monkeypatch.setattr(channel_handoff, "generate_draft", generate_draft)

    draft = await channel_handoff.fill_escalation_draft(
        db_session,
        conversation_id=conversation.id,
        query="как провести документ?",
    )

    assert draft == "Уже заполнен"
    generate_draft.assert_not_awaited()
    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed is not None
    assert refreshed.suggested_response == "Уже заполнен"


async def test_should_draft_followup_true_for_agent_escalated(
    db_session: AsyncSession,
) -> None:
    conversation = await _escalated(db_session)
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    assert await channel_handoff.should_draft_followup(db_session, conversation) is True
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="auto",
    )
    assert (
        await channel_handoff.should_draft_followup(db_session, conversation) is False
    )


async def test_agent_open_operator_followup_escalates(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = Conversation(
        installation_id=_INSTALL,
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.OPERATOR,
            content="уже в диалоге",
        )
    )
    await db_session.commit()
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="agent",
    )
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(return_value="Черновик после оператора"),
    )

    draft = await channel_handoff.persist_draft_followup(
        db_session,
        conversation=conversation,
        user_text="ещё вопрос",
        user_image=None,
    )

    assert draft == "Черновик после оператора"
    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed is not None
    assert refreshed.status == ConversationStatus.ESCALATED
    assert refreshed.suggested_response == "Черновик после оператора"
    escalations = list(
        (
            await db_session.scalars(
                select(Escalation).where(Escalation.conversation_id == conversation.id)
            )
        ).all()
    )
    assert len(escalations) == 1
    assert escalations[0].reason == channel_handoff.AGENT_OPEN_OPERATOR_REASON
    system_rows = list(
        (
            await db_session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.role == MessageRole.SYSTEM,
                )
            )
        ).all()
    )
    assert [row.content for row in system_rows] == [GUEST_ESCALATION_TEXT]


async def test_draft_open_operator_followup_stays_open(
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    conversation = Conversation(
        installation_id=_INSTALL,
        user_id="u1",
        status=ConversationStatus.OPEN,
    )
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.OPERATOR,
            content="уже в диалоге",
        )
    )
    await db_session.commit()
    runtime_settings.update_effective_settings(
        confidence_threshold=0.8,
        operator_assist_mode="draft",
    )
    monkeypatch.setattr(
        channel_handoff,
        "generate_draft",
        AsyncMock(return_value="Черновик draft"),
    )

    await channel_handoff.persist_draft_followup(
        db_session,
        conversation=conversation,
        user_text="ещё вопрос",
        user_image=None,
    )

    refreshed = await db_session.get(Conversation, conversation.id)
    assert refreshed is not None
    assert refreshed.status == ConversationStatus.OPEN
    count = await db_session.scalar(
        select(func.count())
        .select_from(Escalation)
        .where(Escalation.conversation_id == conversation.id)
    )
    assert count == 0
