"""Роутер POST /chat.

На этапе 1 реализована только валидация контракта — без RAG/LangGraph.
Реальная обработка запроса будет подключена на этапе 3.
"""

from uuid import uuid4

from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Принимает сообщение пользователя и возвращает заглушку ответа."""
    return ChatResponse(
        conversation_id=request.conversation_id or uuid4(),
        message_id=request.message_id,
        text="stub: agent pipeline not implemented yet",
        confidence=0.0,
        escalated=False,
        sources=[],
    )
