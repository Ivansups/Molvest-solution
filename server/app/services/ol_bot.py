"""Обработка ONIMBOTMESSAGEADD: окно клиента сценария 1 ТЗ.

Кастомный коннектор (`openlines.py`, channel=bitrix_openlines) не трогаем.
Исходящее — `imbot.message.add`, не `imconnector.send.messages`.
"""

import logging
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.bitrix.oauth import get_current_access_token
from app.channels.bitrix.register_bot import get_current_bot_id
from app.channels.bitrix.rest import (
    Bitrix24RestClient,
    Bitrix24RestError,
    build_rest_client,
)
from app.channels.bitrix.schemas import BitrixBotEvent, BitrixBotResponse
from app.core.config import settings
from app.models.channel import ChannelThread
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus, MessageRole
from app.models.message import Message
from app.rag.retrieval import workspace_to_installation_id
from app.schemas.chat import ChatRequest
from app.services.agent import ConversationConflictError, run_chat_turn

logger = logging.getLogger(__name__)

_CHANNEL = "bitrix_ol_bot"
_CHAT_MSG_NS = UUID("41f7c1f7-0000-4f6e-9c6e-0000000000b3")
_DEFAULT_USER = "bitrix"
_OPERATOR_MARKER = "operator"
_MESSAGE_EVENT = "ONIMBOTMESSAGEADD"


async def process_bot_event(
    session: AsyncSession,
    event: BitrixBotEvent,
) -> BitrixBotResponse:
    """Дубль, эхо бота, welcome, operator или гость."""
    if _is_welcome(event):
        logger.info("бот: welcome/join без вопроса — граф не запускаем")
        return BitrixBotResponse(status="ignored")

    dialog_id = _dialog_id(event)
    message_id = _message_id(event)
    if dialog_id is None or message_id is None:
        raise ConversationConflictError("Событие без DIALOG_ID или MESSAGE_ID")

    existing = await _find_by_channel_message(session, message_id)
    if existing is not None:
        logger.info("дубль %s message_id=%s", _CHANNEL, message_id)
        return BitrixBotResponse(
            conversation_id=existing.conversation_id,
            status="duplicate",
        )

    bot_id = await get_current_bot_id(session)
    if bot_id is not None and _from_user_id(event) == bot_id:
        logger.info("эхо бота id=%s пропущено", bot_id)
        return BitrixBotResponse(status="ignored")

    domain = _domain(event)
    installation_id = workspace_to_installation_id(domain)
    if _is_operator(event):
        return await _process_operator(
            session,
            event=event,
            installation_id=installation_id,
            dialog_id=dialog_id,
            message_id=message_id,
        )
    return await _process_guest(
        session,
        event=event,
        installation_id=installation_id,
        dialog_id=dialog_id,
        message_id=message_id,
    )


async def _process_guest(
    session: AsyncSession,
    *,
    event: BitrixBotEvent,
    installation_id: UUID,
    dialog_id: str,
    message_id: str,
) -> BitrixBotResponse:
    client = _maybe_build_client()
    try:
        return await _run_guest(
            session,
            event=event,
            client=client,
            installation_id=installation_id,
            dialog_id=dialog_id,
            message_id=message_id,
        )
    finally:
        if client is not None:
            await client.aclose()


async def _run_guest(
    session: AsyncSession,
    *,
    event: BitrixBotEvent,
    client: Bitrix24RestClient | None,
    installation_id: UUID,
    dialog_id: str,
    message_id: str,
) -> BitrixBotResponse:
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        dialog_id=dialog_id,
    )
    if mapping is not None:
        conversation = await session.get(Conversation, mapping.conversation_id)
        if conversation is None or conversation.status == ConversationStatus.RESOLVED:
            raise ConversationConflictError("Диалог уже закрыт")
        conversation_id: UUID | None = conversation.id
    else:
        conversation_id = None

    request = ChatRequest(
        message_id=uuid5(_CHAT_MSG_NS, message_id),
        workspace_id=_domain(event),
        conversation_id=conversation_id,
        text=_text(event),
        image_base64=await _fetch_image(event, client),
        user_id=_from_user_id(event) or _DEFAULT_USER,
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
                thread_id=dialog_id,
                installation_id=installation_id,
                conversation_id=response.conversation_id,
            )
        )
        await session.commit()

    if response.escalated:
        logger.info(
            "ol_bot эскалация conversation_id=%s message_id=%s",
            response.conversation_id,
            message_id,
        )
        return BitrixBotResponse(
            conversation_id=response.conversation_id,
            status="processed",
            escalated=True,
        )

    delivered = False
    if response.text:
        delivered = await _send_reply(
            session, client, dialog_id=dialog_id, text=response.text
        )
    logger.info(
        "ol_bot обработано conversation_id=%s delivered=%s message_id=%s",
        response.conversation_id,
        delivered,
        message_id,
    )
    return BitrixBotResponse(
        conversation_id=response.conversation_id,
        status="processed",
        reply=response.text,
        delivered=delivered,
    )


async def _send_reply(
    session: AsyncSession,
    client: Bitrix24RestClient | None,
    *,
    dialog_id: str,
    text: str,
) -> bool:
    if client is None:
        logger.warning("bitrix REST не сконфигурирован: ответ бота не ушёл")
        return False
    bot_id = await get_current_bot_id(session)
    if bot_id is None:
        logger.warning("бот открытой линии не зарегистрирован: ответ не ушёл")
        return False
    access_token = await get_current_access_token(session)
    if access_token is None:
        logger.warning("bitrix приложение не установлено: ответ бота не ушёл")
        return False
    try:
        await client.send_bot_message(
            bot_id=bot_id,
            dialog_id=dialog_id,
            text=text,
            access_token=access_token,
        )
        return True
    except (Bitrix24RestError, OSError) as exc:
        logger.warning("ответ бота не доставлен dialog_id=%s: %s", dialog_id, exc)
        return False


async def _process_operator(
    session: AsyncSession,
    *,
    event: BitrixBotEvent,
    installation_id: UUID,
    dialog_id: str,
    message_id: str,
) -> BitrixBotResponse:
    conversation = await _get_or_create_thread(
        session,
        installation_id=installation_id,
        dialog_id=dialog_id,
        user_id=_from_user_id(event) or _DEFAULT_USER,
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
        "ol_bot оператор conversation_id=%s message_id=%s",
        conversation.id,
        message_id,
    )
    return BitrixBotResponse(
        conversation_id=conversation.id,
        status="processed",
    )


def _maybe_build_client() -> Bitrix24RestClient | None:
    if not (
        settings.bitrix_portal_url
        and settings.bitrix_app_user_id
        and settings.bitrix_app_token
    ):
        return None
    return build_rest_client()


async def _fetch_image(
    event: BitrixBotEvent,
    client: Bitrix24RestClient | None,
) -> str | None:
    url = _first_image_url(event)
    if url is None or client is None:
        return None
    try:
        return await client.download_image(url)
    except (Bitrix24RestError, OSError) as exc:
        logger.warning("вложение бота не скачано: %s", exc)
        return None


def _first_image_url(event: BitrixBotEvent) -> str | None:
    params = event.data.PARAMS if event.data else None
    if params is None:
        return None
    for item in params.FILES:
        url = item.get("url")
        if isinstance(url, str) and url:
            return url
    return None


def _is_welcome(event: BitrixBotEvent) -> bool:
    name = (event.event or _MESSAGE_EVENT).upper()
    if name not in ("", _MESSAGE_EVENT):
        return True
    if _text(event) or _first_image_url(event):
        return False
    return True


def _is_operator(event: BitrixBotEvent) -> bool:
    params = event.data.PARAMS if event.data else None
    if params is None or params.AUTHOR_TYPE is None:
        return False
    return params.AUTHOR_TYPE.lower() == _OPERATOR_MARKER


def _text(event: BitrixBotEvent) -> str | None:
    params = event.data.PARAMS if event.data else None
    return params.MESSAGE if params is not None else None


def _dialog_id(event: BitrixBotEvent) -> str | None:
    params = event.data.PARAMS if event.data else None
    value = params.DIALOG_ID if params is not None else None
    return None if value is None else str(value)


def _message_id(event: BitrixBotEvent) -> str | None:
    params = event.data.PARAMS if event.data else None
    value = params.MESSAGE_ID if params is not None else None
    return None if value is None else str(value)


def _from_user_id(event: BitrixBotEvent) -> str | None:
    params = event.data.PARAMS if event.data else None
    value = params.FROM_USER_ID if params is not None else None
    return None if value is None else str(value)


def _domain(event: BitrixBotEvent) -> str:
    auth = event.auth
    domain = auth.domain if auth is not None else None
    return domain or _DEFAULT_USER


async def _find_by_channel_message(
    session: AsyncSession,
    message_id: str,
) -> Message | None:
    stmt = select(Message).where(
        Message.channel == _CHANNEL,
        Message.channel_message_id == message_id,
    )
    return (await session.scalars(stmt)).first()


async def _find_mapping(
    session: AsyncSession,
    *,
    installation_id: UUID,
    dialog_id: str,
) -> ChannelThread | None:
    stmt = select(ChannelThread).where(
        ChannelThread.channel == _CHANNEL,
        ChannelThread.thread_id == dialog_id,
        ChannelThread.installation_id == installation_id,
    )
    return (await session.scalars(stmt)).first()


async def _get_or_create_thread(
    session: AsyncSession,
    *,
    installation_id: UUID,
    dialog_id: str,
    user_id: str,
) -> Conversation:
    mapping = await _find_mapping(
        session,
        installation_id=installation_id,
        dialog_id=dialog_id,
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
            thread_id=dialog_id,
            installation_id=installation_id,
            conversation_id=conversation.id,
        )
    )
    return conversation
