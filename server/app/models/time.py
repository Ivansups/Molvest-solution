"""UTC-время для колонок моделей."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Текущий момент в UTC с таймзоной."""
    return datetime.now(UTC)
