"""Запуск диалогового графа для одного сообщения чата с персистом диалога."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_graph
from app.agent.state import AgentState, HistoryTurn, RetrievedChunk
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.models.time import utc_now
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.selectors.conversations import list_recent_messages
from app.services.channel_handoff import (
    fill_escalation_draft,
    persist_draft_followup,
)
from app.services.conversations import (
    GUEST_ESCALATION_TEXT,
    IMAGE_HOLD_TEXT,
    persist_guest_hold,
    persist_turn,
)
from app.services.runtime_settings import (
    AssistMode,
    get_effective_operator_assist_mode,
)

# Причина эскалации, когда режим agent удерживает готовый ответ ИИ.
AGENT_HOLD_REASON = "Режим agent: ответ ИИ ждёт подтверждения оператора"
# Текст кнопки «Позвать оператора» в виджете — повтор не должен перетирать черновик.
_GUEST_HANDOFF_TEXT = "Позовите оператора"

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 4


class ConversationConflictError(Exception):
    """Диалог нельзя продолжить этим ходом (resolved или конфликт статуса)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class GuestReplyDecision:
    """Что отдать гостю и что записать после графа."""

    escalated: bool
    guest_text: str
    persist_sources: list[Source]
    escalation_reason: str | None
    suggested_response: str | None
    fill_draft_after_commit: bool


def apply_operator_reply_policy(
    *,
    mode: AssistMode,
    intent: str,
    graph_escalated: bool,
    answer: str,
    sources: list[Source],
    graph_escalation_reason: str,
) -> GuestReplyDecision:
    """Шлюз выдачи: слать гостю, эскалировать или удержать ответ в черновике.

    Роутеры и канальные адаптеры не ветвят режим — смотрят `escalated`.
    """
    if mode == "agent" and not graph_escalated and intent != "empty":
        return GuestReplyDecision(
            escalated=True,
            guest_text=GUEST_ESCALATION_TEXT,
            persist_sources=[],
            escalation_reason=AGENT_HOLD_REASON,
            suggested_response=answer or None,
            fill_draft_after_commit=False,
        )
    if graph_escalated:
        return GuestReplyDecision(
            escalated=True,
            guest_text=GUEST_ESCALATION_TEXT,
            persist_sources=[],
            escalation_reason=graph_escalation_reason or None,
            suggested_response=None,
            fill_draft_after_commit=mode == "agent" and intent != "handoff",
        )
    return GuestReplyDecision(
        escalated=False,
        guest_text=answer,
        persist_sources=sources,
        escalation_reason=None,
        suggested_response=None,
        fill_draft_after_commit=False,
    )


async def run_chat_turn(
    request: ChatRequest,
    session: AsyncSession,
    *,
    channel: str | None = None,
    channel_message_id: str | None = None,
) -> ChatResponse:
    """Прогоняет запрос через LangGraph, пишет диалог и мапит в контракт."""
    turn_started_at = utc_now()
    installation_id = workspace_to_installation_id(request.workspace_id)
    existing = await _load_conversation(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
    )
    if existing is not None and existing.status == ConversationStatus.RESOLVED:
        raise ConversationConflictError("Диалог уже закрыт")
    mode = get_effective_operator_assist_mode()
    if (
        existing is not None
        and existing.status == ConversationStatus.ESCALATED
        and mode == "draft"
    ):
        await persist_guest_hold(
            session,
            conversation=existing,
            user_text=_hold_user_text(request),
            user_image=None,
            user_created_at=turn_started_at,
            channel=channel,
            channel_message_id=channel_message_id,
        )
        logger.info(
            "draft hold conversation_id=%s без графа",
            existing.id,
        )
        return ChatResponse(
            conversation_id=existing.id,
            message_id=request.message_id,
            text=GUEST_ESCALATION_TEXT,
            confidence=0.0,
            escalated=True,
            sources=[],
        )
    if (
        existing is not None
        and existing.status == ConversationStatus.ESCALATED
        and mode == "agent"
    ):
        if _is_repeat_handoff(request):
            await persist_guest_hold(
                session,
                conversation=existing,
                user_text=_hold_user_text(request),
                user_image=None,
                user_created_at=turn_started_at,
                channel=channel,
                channel_message_id=channel_message_id,
            )
            logger.info(
                "agent повторный handoff conversation_id=%s без смены черновика",
                existing.id,
            )
        else:
            await persist_draft_followup(
                session,
                conversation=existing,
                user_text=_hold_user_text(request),
                user_image=None,
                channel=channel,
                channel_message_id=channel_message_id,
            )
            logger.info(
                "agent follow-up conversation_id=%s черновик без ответа гостю",
                existing.id,
            )
        return ChatResponse(
            conversation_id=existing.id,
            message_id=request.message_id,
            text=GUEST_ESCALATION_TEXT,
            confidence=0.0,
            escalated=True,
            sources=[],
        )

    history = await _load_history(session, existing)
    logger.info(
        "граф старт message_id=%s installation_id=%s history=%s status=%s",
        request.message_id,
        installation_id,
        len(history),
        existing.status.value if existing is not None else "open",
    )
    await session.commit()
    final = await get_graph().ainvoke(_initial_state(request, installation_id, history))
    logger.info(
        "граф конец message_id=%s intent=%s escalated=%s confidence=%s",
        request.message_id,
        final.get("intent"),
        final.get("escalated"),
        final.get("confidence"),
    )

    existing = await _load_conversation(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
    )
    if existing is not None and existing.status == ConversationStatus.RESOLVED:
        raise ConversationConflictError("Диалог уже закрыт")

    sources = _to_sources(final.get("chunks") or [])
    graph_escalated = bool(final.get("escalated", False))
    confidence = float(final.get("confidence", 0.0))
    answer = final.get("answer") or ""
    user_text = _user_content(request, final)
    if (
        existing is not None
        and existing.status == ConversationStatus.ESCALATED
        and graph_escalated
    ):
        await persist_guest_hold(
            session,
            conversation=existing,
            user_text=user_text,
            user_image=None,
            user_created_at=turn_started_at,
            channel=channel,
            channel_message_id=channel_message_id,
        )
        return ChatResponse(
            conversation_id=existing.id,
            message_id=request.message_id,
            text=GUEST_ESCALATION_TEXT,
            confidence=confidence,
            escalated=True,
            sources=[],
        )

    decision = apply_operator_reply_policy(
        mode=mode,
        intent=str(final.get("intent") or ""),
        graph_escalated=graph_escalated,
        answer=answer,
        sources=sources,
        graph_escalation_reason=str(final.get("escalation_reason") or ""),
    )

    persisted = await persist_turn(
        session,
        conversation_id=request.conversation_id,
        installation_id=installation_id,
        user_id=request.user_id,
        user_text=user_text,
        user_image=None,
        assistant_content=decision.guest_text,
        confidence=confidence,
        escalated=decision.escalated,
        sources=decision.persist_sources,
        escalation_reason=decision.escalation_reason,
        suggested_response=decision.suggested_response,
        user_created_at=turn_started_at,
        channel=channel,
        channel_message_id=channel_message_id,
    )
    if decision.fill_draft_after_commit:
        await fill_escalation_draft(
            session,
            conversation_id=persisted.conversation.id,
            query=user_text,
        )

    return ChatResponse(
        conversation_id=persisted.conversation.id,
        message_id=request.message_id,
        text=decision.guest_text,
        confidence=confidence,
        escalated=decision.escalated,
        sources=decision.persist_sources,
    )


def _is_repeat_handoff(request: ChatRequest) -> bool:
    """Повтор «Позвать оператора» в эскалированном диалоге — черновик не трогаем."""
    if request.force_handoff:
        return True
    text = (request.text or "").strip()
    return text == _GUEST_HANDOFF_TEXT


def _hold_user_text(request: ChatRequest) -> str | None:
    """Текст гостя в draft-hold: без vision, картинка не пишется в image_url."""
    if request.text and request.text.strip():
        return request.text
    if request.image_base64:
        return IMAGE_HOLD_TEXT
    return request.text


def _user_content(request: ChatRequest, final: dict[str, object]) -> str | None:
    """Реплика пользователя для БД — `query`, а не сырой текст.

    `query` после vision содержит описание скриншота, а сам скриншот не
    сохраняется: `Message.image_url` рассчитан на ссылку, а не на base64.
    Без описания у сообщения с одной картинкой не осталось бы содержимого.
    """
    query = final.get("query")
    if isinstance(query, str) and query:
        return query
    return request.text


async def _load_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID | None,
    installation_id: UUID,
) -> Conversation | None:
    if conversation_id is None:
        return None
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.installation_id != installation_id:
        return None
    return conversation


async def _load_history(
    session: AsyncSession,
    conversation: Conversation | None,
) -> list[HistoryTurn]:
    if conversation is None:
        return []
    rows = await list_recent_messages(session, conversation.id, limit=_HISTORY_LIMIT)
    return [HistoryTurn(role=row.role.value, content=row.content) for row in rows]


def _initial_state(
    request: ChatRequest,
    installation_id: UUID,
    history: list[HistoryTurn],
) -> AgentState:
    return {
        "text": request.text,
        "image_base64": request.image_base64,
        "installation_id": str(installation_id),
        "query": "",
        "intent": "empty",
        "history": history,
        "chunks": [],
        "answer": "",
        "confidence": 0.0,
        "escalated": False,
        "escalation_reason": "",
        "force_handoff": bool(request.force_handoff),
    }


def _to_sources(chunks: list[RetrievedChunk]) -> list[Source]:
    sources: list[Source] = []
    for chunk in chunks:
        sources.append(
            Source(
                document_id=UUID(chunk["document_id"]),
                title=chunk["title"],
                chunk_text=chunk["chunk_text"],
            )
        )
    return sources
