"""REST настроек агента: порог, режим и правила эскалации."""

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


def _to_out() -> AgentSettingsOut:
    """Мапит эффективный снимок в контракт панели."""
    snap = runtime_settings.get_effective_settings()
    return AgentSettingsOut(
        confidence_threshold=snap.confidence_threshold,
        operator_assist_mode=snap.operator_assist_mode,
        escalate_on_detector_failure=snap.escalate_on_detector_failure,
        escalate_on_low_rag=snap.escalate_on_low_rag,
        skip_low_rag_on_image=snap.skip_low_rag_on_image,
        escalate_on_guest_handoff=snap.escalate_on_guest_handoff,
    )


@router.get("/settings")
async def get_settings_route() -> AgentSettingsOut:
    """Текущие эффективные порог, режим и правила (env или runtime override)."""
    return _to_out()


@router.put("/settings")
async def put_settings_route(
    body: AgentSettingsUpdate, session: SessionDep
) -> AgentSettingsOut:
    """Обновляет эффективные настройки и сохраняет их — переживают рестарт."""
    runtime_settings.update_effective_settings(
        confidence_threshold=body.confidence_threshold,
        operator_assist_mode=body.operator_assist_mode,
        escalate_on_detector_failure=body.escalate_on_detector_failure,
        escalate_on_low_rag=body.escalate_on_low_rag,
        skip_low_rag_on_image=body.skip_low_rag_on_image,
        escalate_on_guest_handoff=body.escalate_on_guest_handoff,
    )
    await runtime_settings.persist_effective_settings(session)
    logger.info(
        "настройки обновлены threshold=%s mode=%s",
        body.confidence_threshold,
        body.operator_assist_mode,
    )
    return _to_out()
