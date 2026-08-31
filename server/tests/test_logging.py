"""Юнит-тесты утилиты превью для логов."""

from app.core.logging import preview


def test_preview_keeps_short_text() -> None:
    assert preview("привет") == "привет"


def test_preview_collapses_whitespace_and_truncates() -> None:
    text = "один\nдва  " + ("слово " * 30)
    result = preview(text, limit=20)
    assert "\n" not in result
    assert len(result) <= 20
    assert result.endswith("…")
