"""Роутер POST /chat — валидация контракта и вызов графа агента."""

from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import run_chat_turn

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Принимает сообщение пользователя и прогоняет его через LangGraph."""
    return await run_chat_turn(request)
