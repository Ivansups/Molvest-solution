"""Эффективные настройки агента: env-дефолт + runtime override в процессе."""

from typing import Literal

from app.core.config import settings

AssistMode = Literal["draft", "auto", "agent"]

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
    """Сохраняет runtime-значения до рестарта процесса API."""
    global _override_threshold, _override_assist_mode
    _override_threshold = confidence_threshold
    _override_assist_mode = operator_assist_mode


def reset_effective_settings() -> None:
    """Сбрасывает override (тесты и возврат к env после рестарта логики)."""
    global _override_threshold, _override_assist_mode
    _override_threshold = None
    _override_assist_mode = None
