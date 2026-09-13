"""Схемы панели настроек агента (порог, режим и правила эскалации)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class AgentSettingsOut(BaseModel):
    """Текущие настройки, которые видит админ в панели."""

    confidence_threshold: float = Field(ge=0.0, le=1.0)
    operator_assist_mode: Literal["draft", "auto", "agent"]
    escalate_on_detector_failure: bool
    escalate_on_low_rag: bool
    skip_low_rag_on_image: bool
    escalate_on_guest_handoff: bool


class AgentSettingsUpdate(BaseModel):
    """Обновление настроек из панели администратора."""

    model_config = ConfigDict(extra="ignore")

    confidence_threshold: float = Field(ge=0.5, le=0.99)
    operator_assist_mode: Literal["draft", "auto", "agent"]
    # StrictBool: строки вроде "yes" не коерсятся в True (иначе PUT даёт 200).
    escalate_on_detector_failure: StrictBool
    escalate_on_low_rag: StrictBool
    skip_low_rag_on_image: StrictBool
    escalate_on_guest_handoff: StrictBool
