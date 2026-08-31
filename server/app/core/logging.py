"""Настройка логирования с request_id для трассировки запросов."""

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Подставляет request_id текущего запроса в каждую строку лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    """Настраивает логирование в stdout с request_id."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] [%(request_id)s] %(message)s",
        handlers=[handler],
        force=True,
    )


def preview(text: str, limit: int = 80) -> str:
    """Короткий фрагмент для лога: без переносов, обрезка с многоточием."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
