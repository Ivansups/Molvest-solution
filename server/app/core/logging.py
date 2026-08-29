"""Настройка логирования с correlation_id для трассировки запросов."""

import logging
import sys


def setup_logging() -> None:
    """Настраивает базовое логирование в stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
