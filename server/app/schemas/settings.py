"""Схемы панели настроек агента (порог и режим эскалации)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentSettingsOut(BaseModel):
    """Текущие настройки, которые видит админ в панели."""

    confidence_threshold: float = Field(ge=0.0, le=1.0)
    operator_assist_mode: Literal["draft", "auto"]


class AgentSettingsUpdate(BaseModel):
    """Обновление настроек из панели администратора."""

    model_config = ConfigDict(extra="ignore")

    confidence_threshold: float = Field(ge=0.5, le=0.99)
    operator_assist_mode: Literal["draft", "auto"]
