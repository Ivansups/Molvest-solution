"""Retrieve + generate черновика оператора, общий для консоли и live-треда."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.generate import generate
from app.agent.state import AgentState, HistoryTurn
from app.core.config import settings
from app.core.gigachat_client import get_gigachat_service
from app.models.conversation import Conversation
from app.rag.retrieval import make_retriever
from app.selectors.conversations import list_recent_messages

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 4


async def generate_draft(
    session: AsyncSession,
    *,
    conversation: Conversation,
    query: str,
) -> str | None:
    """Считает текст черновика по последним репликам диалога.

    Статус и `suggested_response` не трогает — ленту оставляет нетронутой.
    """
    history_rows = await list_recent_messages(
        session, conversation.id, limit=_HISTORY_LIMIT
    )
    history = [
        HistoryTurn(role=row.role.value, content=row.content) for row in history_rows
    ]
    await session.commit()

    state: AgentState = {
        "query": query,
        "history": history,
        "chunks": [],
        "installation_id": str(conversation.installation_id),
    }
    llm = get_gigachat_service()
    retriever = make_retriever(llm, settings)
    state["chunks"] = await retriever(state)
    result = await generate(state, llm=llm)
    answer = result.get("answer")
    logger.info("черновик посчитан conversation_id=%s", conversation.id)
    return answer if isinstance(answer, str) and answer else None
