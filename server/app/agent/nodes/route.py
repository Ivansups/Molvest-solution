"""Ветвление по порогу уверенности из конфига — не из узлов и сценариев."""

from app.agent.state import AgentState
from app.core.config import Settings


async def route(state: AgentState, *, settings: Settings) -> dict[str, bool]:
    """escalated=True, если уверенность ниже порога."""
    confidence = state.get("confidence", 0.0)
    return {"escalated": confidence < settings.confidence_threshold}
