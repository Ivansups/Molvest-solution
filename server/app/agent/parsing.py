"""Разбор JSON-ответов модели в узлах classify и confidence_check."""

import json
from typing import cast

from app.agent.state import Intent

_INTENT_VALUES = {"greeting", "off_topic", "support"}


def extract_json_object(text: str) -> dict[str, object]:
    """Достаёт первый JSON-объект из текста модели."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("в ответе модели нет JSON-объекта")
    data: object = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON модели не является объектом")
    return cast(dict[str, object], data)


def parse_intent(raw: str) -> Intent:
    """Читает intent; неизвестное значение считаем support, чтобы пойти в RAG."""
    try:
        intent = str(extract_json_object(raw).get("intent", "")).strip().lower()
    except (ValueError, json.JSONDecodeError):
        return "support"
    if intent in _INTENT_VALUES:
        return cast(Intent, intent)
    return "support"


def parse_confidence(raw: str) -> float:
    """Читает уверенность 0..1; при ошибке разбора — 0 (эскалация)."""
    try:
        raw_value = extract_json_object(raw)["confidence"]
    except (ValueError, KeyError, json.JSONDecodeError):
        return 0.0
    if not isinstance(raw_value, int | float) or isinstance(raw_value, bool):
        return 0.0
    return min(1.0, max(0.0, float(raw_value)))
