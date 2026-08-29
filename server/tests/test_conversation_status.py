"""Переходы статуса диалога — без обращения к БД."""

import pytest

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.services.conversation_status import (
    IllegalStatusTransitionError,
    transition_status,
)


def test_open_to_escalated() -> None:
    conversation = Conversation(status=ConversationStatus.OPEN)
    transition_status(conversation, ConversationStatus.ESCALATED)
    assert conversation.status is ConversationStatus.ESCALATED


def test_escalated_to_resolved() -> None:
    conversation = Conversation(status=ConversationStatus.ESCALATED)
    transition_status(conversation, ConversationStatus.RESOLVED)
    assert conversation.status is ConversationStatus.RESOLVED


def test_open_to_resolved_is_illegal() -> None:
    conversation = Conversation(status=ConversationStatus.OPEN)
    with pytest.raises(IllegalStatusTransitionError):
        transition_status(conversation, ConversationStatus.RESOLVED)
    assert conversation.status is ConversationStatus.OPEN


def test_escalated_to_open_is_illegal() -> None:
    conversation = Conversation(status=ConversationStatus.ESCALATED)
    with pytest.raises(IllegalStatusTransitionError):
        transition_status(conversation, ConversationStatus.OPEN)
    assert conversation.status is ConversationStatus.ESCALATED
