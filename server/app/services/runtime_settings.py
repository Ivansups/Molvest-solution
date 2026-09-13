"""Эффективные настройки агента: env-дефолт + runtime override в процессе.

Override живёт в памяти процесса — читают его синхронно из доброго десятка
мест графа и каналов, лишний `await` туда тянуть не хочется. В Postgres
(`agent_settings`, одна строка id=1) он зеркалится отдельно: `PUT /api/settings`
дополнительно пишет через `persist_effective_settings`, а при старте API
`load_persisted_settings` подтягивает последнее сохранённое значение обратно
в память — иначе override не переживает рестарт процесса.
"""

import logging
from dataclasses import dataclass, replace
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_settings import AgentSettings

logger = logging.getLogger(__name__)

AssistMode = Literal["draft", "auto", "agent"]

_SINGLETON_ID = 1


@dataclass(frozen=True)
class EffectiveSettings:
    """Снимок эффективных настроек: порог, режим и правила эскалации."""

    confidence_threshold: float
    operator_assist_mode: AssistMode
    escalate_on_detector_failure: bool
    escalate_on_low_rag: bool
    skip_low_rag_on_image: bool
    escalate_on_guest_handoff: bool


_override: EffectiveSettings | None = None


def _from_env() -> EffectiveSettings:
    """Дефолт процесса из env — пока админ не сохранил override."""
    return EffectiveSettings(
        confidence_threshold=settings.confidence_threshold,
        operator_assist_mode=settings.operator_assist_mode,
        escalate_on_detector_failure=settings.escalate_on_detector_failure,
        escalate_on_low_rag=settings.escalate_on_low_rag,
        skip_low_rag_on_image=settings.skip_low_rag_on_image,
        escalate_on_guest_handoff=settings.escalate_on_guest_handoff,
    )


def get_effective_settings() -> EffectiveSettings:
    """Эффективный снимок: runtime override или env."""
    return _override if _override is not None else _from_env()


def get_effective_operator_assist_mode() -> AssistMode:
    """Режим черновика оператора: override из панели или env."""
    return get_effective_settings().operator_assist_mode


def update_effective_settings(
    *,
    confidence_threshold: float,
    operator_assist_mode: AssistMode,
    escalate_on_detector_failure: bool | None = None,
    escalate_on_low_rag: bool | None = None,
    skip_low_rag_on_image: bool | None = None,
    escalate_on_guest_handoff: bool | None = None,
) -> None:
    """Применяет runtime-значения в памяти немедленно, без ожидания БД.

    Новые правила можно не передавать: тогда берётся текущее эффективное
    значение. Так старые тесты и вызовы с порогом/режимом не ломаются.
    """
    global _override
    current = get_effective_settings()
    overrides = {
        "escalate_on_detector_failure": escalate_on_detector_failure,
        "escalate_on_low_rag": escalate_on_low_rag,
        "skip_low_rag_on_image": skip_low_rag_on_image,
        "escalate_on_guest_handoff": escalate_on_guest_handoff,
    }
    _override = replace(
        current,
        confidence_threshold=confidence_threshold,
        operator_assist_mode=operator_assist_mode,
        **{k: v for k, v in overrides.items() if v is not None},
    )


def reset_effective_settings() -> None:
    """Сбрасывает override (тесты и возврат к env после рестарта логики)."""
    global _override
    _override = None


async def persist_effective_settings(session: AsyncSession) -> None:
    """Пишет текущий override в БД, чтобы он пережил рестарт API."""
    if _override is None:
        return
    stmt = insert(AgentSettings).values(
        id=_SINGLETON_ID,
        confidence_threshold=_override.confidence_threshold,
        operator_assist_mode=_override.operator_assist_mode,
        escalate_on_detector_failure=_override.escalate_on_detector_failure,
        escalate_on_low_rag=_override.escalate_on_low_rag,
        skip_low_rag_on_image=_override.skip_low_rag_on_image,
        escalate_on_guest_handoff=_override.escalate_on_guest_handoff,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AgentSettings.id],
        set_={
            "confidence_threshold": stmt.excluded.confidence_threshold,
            "operator_assist_mode": stmt.excluded.operator_assist_mode,
            "escalate_on_detector_failure": (
                stmt.excluded.escalate_on_detector_failure
            ),
            "escalate_on_low_rag": stmt.excluded.escalate_on_low_rag,
            "skip_low_rag_on_image": stmt.excluded.skip_low_rag_on_image,
            "escalate_on_guest_handoff": stmt.excluded.escalate_on_guest_handoff,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def load_persisted_settings(session: AsyncSession) -> None:
    """При старте API подтягивает последний сохранённый override из БД."""
    row = (
        await session.execute(
            select(AgentSettings).where(AgentSettings.id == _SINGLETON_ID)
        )
    ).scalar_one_or_none()
    if row is None:
        return
    update_effective_settings(
        confidence_threshold=row.confidence_threshold,
        operator_assist_mode=cast("AssistMode", row.operator_assist_mode),
        escalate_on_detector_failure=row.escalate_on_detector_failure,
        escalate_on_low_rag=row.escalate_on_low_rag,
        skip_low_rag_on_image=row.skip_low_rag_on_image,
        escalate_on_guest_handoff=row.escalate_on_guest_handoff,
    )
    logger.info(
        "настройки восстановлены из БД threshold=%s mode=%s",
        row.confidence_threshold,
        row.operator_assist_mode,
    )
