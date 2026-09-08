"""Обработка событий открытой линии Bitrix24 (сценарий 1).

Входящее сообщение гостя: маппинг id диалога ОЛ → `conversation_id`,
прогон через общий `run_chat_turn` (как `POST /chat`, без дублирования графа)
и исходящая отправка ответа в тот же диалог через REST после фиксации состояния.
Операторские события пишутся в ленту без запуска графа и без исходящих вызовов.
"""

import logging
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.attachments import (
    fetch_attachment_base64,
    first_image_ref,
)
from app.channels.bitrix.notify import try_send_operator_note
from app.channels.bitrix.oauth import get_current_access_token
from app.channels.bitrix.rest import (
    Bitrix24RestClient,
    Bitrix24RestError,
    maybe_build_rest_client,
)
from app.channels.bitrix.schemas import (
    BitrixOpenLinesEvent,
    BitrixOpenLinesResponse,
)
from app.core.config import settings
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest
from app.services.agent import ConversationConflictError, run_chat_turn
from app.services.channel_handoff import (
    fill_escalation_draft,
    persist_draft_followup,
    should_draft_followup,
)

logger = logging.getLogger(__name__)

_CHANNEL = "bitrix_openlines"
_CHAT_MSG_NS = UUID("41f7c1f7-0000-4f6e-9c6e-0000000000a2")
_DEFAULT_USER = "bitrix"
_OPERATOR_MARKER = "operator"


async def process_openlines_event(
    session: AsyncSession,
    event: BitrixOpenLinesEvent,
) -> BitrixOpenLinesResponse:
    """Обрабатывает одно событие открытой линии: дубль, operator, гость."""
    chat_id = _chat_id(event)
    message_id = _message_id(event)
    if chat_id is None or message_id is None:
        raise ConversationConflictError("Событие без chat_id или message_id")

    existing = await _find_by_channel_message(session, message_id)
    if existing is not None:
        logger.info("дубль %s message_id=%s", _CHANNEL, message_id)
        return BitrixOpenLinesResponse(
            conversation_id=existing.conversation_id,
            status="duplicate",
        )

    domain = _domain(event)
    installation_id = workspace_to_installation_id(domain)
    if _is_operator(event):
        return await _process_operator(
            session,
            event=event,
            installation_id=installation_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    return await _process_guest(
        session,
        event=event,
        installation_id=installation_id,
        chat_id=chat_id,
        message_id=message_id,
    )


async def _process_guest(
    session: AsyncSession,
    *,
    event: BitrixOpenLinesEvent,
    installation_id: UUID,
    chat_id: str,
    message_id: str,
) -> BitrixOpenLinesResponse:
    """Полный граф: ответ гостю при высоком confidence, иначе эскалация."""
    client = maybe_build_rest_client()
    try:
        return await _run_guest(
            session,
            event=event,
            client=client,
            installation_id=installation_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    finally:
        if client is not None:
            await client.aclose()


async def _run_guest(
    session: AsyncSession,
    *,
    event: BitrixOpenLinesEvent,
    client: Bitrix24RestClient | None,
    installation_id: UUID,
    chat_id: str,
    message_id: str,
) -> BitrixOpenLinesResponse:
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        chat_id=chat_id,
    )
    conversation: Conversation | None = None
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None or conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        if await should_draft_followup(session, conversation):
            url, file_id = _image_ref(event)
            image = await fetch_attachment_base64(
                client=client, session=session, url=url, file_id=file_id
            )
            draft = await persist_draft_followup(
                session,
                conversation=conversation,
                user_text=_text(event),
                user_image=image,
                channel=_CHANNEL,
                channel_message_id=message_id,
            )
            await try_send_operator_note(session, client, dialog_id=chat_id, text=draft)
            return BitrixOpenLinesResponse(
                conversation_id=conversation.id,
                status="processed",
                escalated=conversation.status == ConversationStatus.ESCALATED,
            )

    url, file_id = _image_ref(event)
    request = ChatRequest(
        message_id=uuid5(_CHAT_MSG_NS, message_id),
        workspace_id=_domain(event),
        conversation_id=None if conversation is None else conversation.id,
        text=_text(event),
        image_base64=await fetch_attachment_base64(
            client=client, session=session, url=url, file_id=file_id
        ),
        user_id=_author_id(event),
    )
    response = await run_chat_turn(
        request,
        session,
        channel=_CHANNEL,
        channel_message_id=message_id,
    )

    if mapping is None:
        session.add(
            ChannelThread(
                channel=_CHANNEL,
                thread_id=chat_id,
                installation_id=installation_id,
                conversation_id=response.conversation_id,
            )
        )
        await session.commit()

    if response.escalated:
        logger.info(
            "openlines эскалация conversation_id=%s message_id=%s",
            response.conversation_id,
            message_id,
        )
        draft = await fill_escalation_draft(
            session,
            conversation_id=response.conversation_id,
            query=_text(event),
        )
        await try_send_operator_note(session, client, dialog_id=chat_id, text=draft)
        return BitrixOpenLinesResponse(
            conversation_id=response.conversation_id,
            status="processed",
            escalated=True,
        )

    delivered = False
    if response.text:
        delivered = await _send_reply(
            session, client, chat_id=chat_id, text=response.text
        )
    logger.info(
        "openlines обработано conversation_id=%s delivered=%s message_id=%s",
        response.conversation_id,
        delivered,
        message_id,
    )
    return BitrixOpenLinesResponse(
        conversation_id=response.conversation_id,
        status="processed",
        reply=response.text,
        delivered=delivered,
    )


async def _send_reply(
    session: AsyncSession,
    client: Bitrix24RestClient | None,
    *,
    chat_id: str,
    text: str,
) -> bool:
    """Отправляет ответ в диалог ОЛ; недоступность не роняет обработку события."""
    if client is None:
        logger.warning("bitrix REST не сконфигурирован: ответ в ОЛ не ушёл")
        return False
    connector_id = settings.bitrix_connector_id
    if not connector_id:
        logger.warning("BITRIX_CONNECTOR_ID пуст: ответ в ОЛ не ушёл")
        return False
    access_token = await get_current_access_token(session)
    if access_token is None:
        logger.warning("bitrix приложение не установлено: ответ в ОЛ не ушёл")
        return False
    try:
        await client.send_message(
            connector_id=connector_id,
            chat_id=chat_id,
            text=text,
            access_token=access_token,
        )
        return True
    except (Bitrix24RestError, OSError) as exc:
        logger.warning("ответ не доставлен в ОЛ chat_id=%s: %s", chat_id, exc)
        return False


async def _process_operator(
    session: AsyncSession,
    *,
    event: BitrixOpenLinesEvent,
    installation_id: UUID,
    chat_id: str,
    message_id: str,
) -> BitrixOpenLinesResponse:
    """Пассивная запись сообщения оператора: граф и исходящий REST не вызываются."""
    conversation = await _get_or_create_thread(
        session,
        installation_id=installation_id,
        chat_id=chat_id,
        user_id=_author_id(event),
    )
    session.add(
        Message(
            conversation=conversation,
            role=MessageRole.OPERATOR,
            content=_text(event) or "",
            channel=_CHANNEL,
            channel_message_id=message_id,
        )
    )
    await session.commit()
    logger.info(
        "сообщение оператора conversation_id=%s message_id=%s",
        conversation.id,
        message_id,
    )
    return BitrixOpenLinesResponse(
        conversation_id=conversation.id,
        status="processed",
    )


def _image_ref(event: BitrixOpenLinesEvent) -> tuple[str | None, str | None]:
    message = event.data.message if event.data else None
    if message is None:
        return None, None
    url, file_id = first_image_ref(message.img)
    if url or file_id:
        return url, file_id
    return first_image_ref(message.files)


def _is_operator(event: BitrixOpenLinesEvent) -> bool:
    """Классификация по типу автора; отсутствие типа — гость."""
    message = event.data.message if event.data else None
    if message is None:
        return False
    author = getattr(message, "author", None)
    value = author.type if author is not None else None
    return value is not None and str(value).lower() == _OPERATOR_MARKER


def _author_id(event: BitrixOpenLinesEvent) -> str:
    message = event.data.message if event.data else None
    author = getattr(message, "author", None) if message else None
    value: str | int | None = author.id if author is not None else None
    if value is None and message is not None:
        value = message.user_id
    return _DEFAULT_USER if value is None else str(value)


def _text(event: BitrixOpenLinesEvent) -> str | None:
    message = event.data.message if event.data else None
    return message.text if message is not None else None


def _domain(event: BitrixOpenLinesEvent) -> str:
    auth = event.auth
    domain = auth.domain if auth is not None else None
    return domain or _DEFAULT_USER


def _chat_id(event: BitrixOpenLinesEvent) -> str | None:
    connector = event.data.connector if event.data else None
    value = connector.chat_id if connector is not None else None
    return None if value is None else str(value)


def _message_id(event: BitrixOpenLinesEvent) -> str | None:
    message = event.data.message if event.data else None
    value = message.id if message is not None else None
    return None if value is None else str(value)


async def _find_by_channel_message(
    session: AsyncSession,
    message_id: str,
) -> Message | None:
    """Ранняя проверка идемпотентности: дубль — без графа и персиста."""
    stmt = select(Message).where(
        Message.channel == _CHANNEL,
        Message.channel_message_id == message_id,
    )
    return (await session.scalars(stmt)).first()


async def _find_mapping(
    session: AsyncSession,
    *,
    installation_id: UUID,
    chat_id: str,
) -> ChannelThread | None:
    stmt = select(ChannelThread).where(
        ChannelThread.channel == _CHANNEL,
        ChannelThread.thread_id == chat_id,
        ChannelThread.installation_id == installation_id,
    )
    return (await session.scalars(stmt)).first()


async def _get_or_create_thread(
    session: AsyncSession,
    *,
    installation_id: UUID,
    chat_id: str,
    user_id: str,
) -> Conversation:
    """Возвращает диалог сессии; создаёт диалог + маппинг при первом событии."""
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        chat_id=chat_id,
    )
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None:
            conversation = Conversation(
                installation_id=installation_id,
                user_id=user_id,
                status=ConversationStatus.OPEN,
            )
            session.add(conversation)
            await session.flush()
            mapping.conversation_id = conversation.id
            return conversation
        if conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        return conversation

    conversation = Conversation(
        installation_id=installation_id,
        user_id=user_id,
        status=ConversationStatus.OPEN,
    )
    session.add(conversation)
    await session.flush()
    session.add(
        ChannelThread(
            channel=_CHANNEL,
            thread_id=chat_id,
            installation_id=installation_id,
            conversation_id=conversation.id,
        )
    )
    return conversation
