"""Роутер POST /chat — валидация контракта и вызов графа агента."""

import logging

from fastapi import APIRouter

from app.core.logging import preview
from app.db.session import SessionDep
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import run_chat_turn

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat")
async def chat(request: ChatRequest, session: SessionDep) -> ChatResponse:
    """Принимает сообщение пользователя и прогоняет его через LangGraph."""
    logger.info(
        "вход /chat message_id=%s workspace=%s conversation_id=%s has_image=%s text=%s",
        request.message_id,
        request.workspace_id,
        request.conversation_id,
        bool(request.image_base64),
        preview(request.text or ""),
    )
    response = await run_chat_turn(request, session)
    logger.info(
        "выход /chat message_id=%s conversation_id=%s escalated=%s "
        "confidence=%s sources=%s text=%s",
        response.message_id,
        response.conversation_id,
        response.escalated,
        response.confidence,
        len(response.sources),
        preview(response.text),
    )
    return response
