"""REST настроек агента: порог уверенности и режим эскалации."""

import logging

from fastapi import APIRouter, Depends

from app.core.security import require_internal_token
from app.db.session import SessionDep
from app.schemas.settings import AgentSettingsOut, AgentSettingsUpdate
from app.services import runtime_settings

router = APIRouter(
    prefix="/api",
    tags=["settings"],
    dependencies=[Depends(require_internal_token)],
)

logger = logging.getLogger(__name__)


@router.get("/settings")
async def get_settings_route() -> AgentSettingsOut:
    """Текущие эффективные порог и режим (env или runtime override)."""
    return AgentSettingsOut(
        confidence_threshold=runtime_settings.get_effective_confidence_threshold(),
        operator_assist_mode=runtime_settings.get_effective_operator_assist_mode(),
    )


@router.put("/settings")
async def put_settings_route(
    body: AgentSettingsUpdate, session: SessionDep
) -> AgentSettingsOut:
    """Обновляет эффективные настройки и сохраняет их — переживают рестарт."""
    runtime_settings.update_effective_settings(
        confidence_threshold=body.confidence_threshold,
        operator_assist_mode=body.operator_assist_mode,
    )
    await runtime_settings.persist_effective_settings(session)
    logger.info(
        "настройки обновлены threshold=%s mode=%s",
        body.confidence_threshold,
        body.operator_assist_mode,
    )
    return AgentSettingsOut(
        confidence_threshold=runtime_settings.get_effective_confidence_threshold(),
        operator_assist_mode=runtime_settings.get_effective_operator_assist_mode(),
    )
