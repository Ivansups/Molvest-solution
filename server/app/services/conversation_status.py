"""Единственная точка смены Conversation.status."""

import logging

from app.models.conversation import Conversation
from app.models.enums import ConversationStatus

logger = logging.getLogger(__name__)

_ALLOWED: frozenset[tuple[ConversationStatus, ConversationStatus]] = frozenset(
    {
        (ConversationStatus.OPEN, ConversationStatus.ESCALATED),
        (ConversationStatus.ESCALATED, ConversationStatus.RESOLVED),
    }
)


class IllegalStatusTransitionError(Exception):
    """Переход статуса не из разрешённой цепочки."""

    def __init__(
        self,
        current: ConversationStatus,
        target: ConversationStatus,
    ) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Нельзя сменить статус {current} → {target}")


def transition_status(
    conversation: Conversation,
    new_status: ConversationStatus,
) -> Conversation:
    """Меняет статус, если переход open→escalated или escalated→resolved."""
    pair = (conversation.status, new_status)
    if pair not in _ALLOWED:
        logger.warning(
            "запрещённый переход conversation_id=%s %s → %s",
            conversation.id,
            conversation.status,
            new_status,
        )
        raise IllegalStatusTransitionError(conversation.status, new_status)
    logger.info(
        "статус диалога conversation_id=%s %s → %s",
        conversation.id,
        conversation.status,
        new_status,
    )
    conversation.status = new_status
    return conversation
