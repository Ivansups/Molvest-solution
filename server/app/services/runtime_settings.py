"""Эффективные настройки агента: env-дефолт + runtime override в процессе.

Override живёт в памяти процесса — читают его синхронно из доброго десятка
мест графа и каналов, лишний `await` туда тянуть не хочется. В Postgres
(`agent_settings`, одна строка id=1) он зеркалится отдельно: `PUT /api/settings`
дополнительно пишет через `persist_effective_settings`, а при старте API
`load_persisted_settings` подтягивает последнее сохранённое значение обратно
в память — иначе override не переживает рестарт процесса.
"""

import logging
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_settings import AgentSettings

logger = logging.getLogger(__name__)

AssistMode = Literal["draft", "auto", "agent"]

_SINGLETON_ID = 1

_override_threshold: float | None = None
_override_assist_mode: AssistMode | None = None


def get_effective_confidence_threshold() -> float:
    """Порог эскалации: override из панели или значение из env."""
    if _override_threshold is not None:
        return _override_threshold
    return settings.confidence_threshold


def get_effective_operator_assist_mode() -> AssistMode:
    """Режим черновика оператора: override из панели или env."""
    if _override_assist_mode is not None:
        return _override_assist_mode
    return settings.operator_assist_mode


def update_effective_settings(
    *,
    confidence_threshold: float,
    operator_assist_mode: AssistMode,
) -> None:
    """Применяет runtime-значения в памяти немедленно, без ожидания БД."""
    global _override_threshold, _override_assist_mode
    _override_threshold = confidence_threshold
    _override_assist_mode = operator_assist_mode


def reset_effective_settings() -> None:
    """Сбрасывает override (тесты и возврат к env после рестарта логики)."""
    global _override_threshold, _override_assist_mode
    _override_threshold = None
    _override_assist_mode = None


async def persist_effective_settings(session: AsyncSession) -> None:
    """Пишет текущий override в БД, чтобы он пережил рестарт API."""
    if _override_threshold is None or _override_assist_mode is None:
        return
    stmt = insert(AgentSettings).values(
        id=_SINGLETON_ID,
        confidence_threshold=_override_threshold,
        operator_assist_mode=_override_assist_mode,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AgentSettings.id],
        set_={
            "confidence_threshold": stmt.excluded.confidence_threshold,
            "operator_assist_mode": stmt.excluded.operator_assist_mode,
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
    )
    logger.info(
        "настройки восстановлены из БД threshold=%s mode=%s",
        row.confidence_threshold,
        row.operator_assist_mode,
    )
