"""Персистентный runtime-override порога и режима — одна строка (id=1)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.time import utc_now


class AgentSettings(Base):
    """Синглтон-строка: зеркало runtime_settings, переживает рестарт API."""

    __tablename__ = "agent_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    operator_assist_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
