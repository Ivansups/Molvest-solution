"""Ретривал чанков. Пока заглушка — база знаний ещё не подключена."""

from app.agent.state import AgentState, RetrievedChunk


async def retrieve(state: AgentState) -> dict[str, object]:
    """Вернёт top-k чанки после этапа индексации. Сейчас список пустой."""
    _ = state
    empty: list[RetrievedChunk] = []
    return {"chunks": empty}
