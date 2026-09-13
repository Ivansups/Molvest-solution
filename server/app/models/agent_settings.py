"""Персистентный runtime-override порога, режима и правил эскалации."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.time import utc_now


class AgentSettings(Base):
    """Синглтон-строка: зеркало runtime_settings, переживает рестарт API."""

    __tablename__ = "agent_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    operator_assist_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    escalate_on_detector_failure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    escalate_on_low_rag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    skip_low_rag_on_image: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    escalate_on_guest_handoff: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
