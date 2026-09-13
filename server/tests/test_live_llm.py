"""Живые smoke-вызовы LLM — только локально, не в CI.

Запуск:
  cd server && uv run pytest -m live
  # или из корня: make test-live

Без GIGACHAT_API_KEY / OPENROUTER_API_KEY соответствующие тесты
пропускаются. Обычный `pytest` / CI гоняет `-m "not live"`.
"""

from __future__ import annotations

import pytest

from app.agent.prompts import HANDOFF_SYSTEM_PROMPT
from app.core.config import Settings
from app.core.gigachat_client import GigaChatService
from app.core.openrouter_client import OpenRouterClassifier
from app.models.chunk import EMBEDDING_DIMENSIONS

pytestmark = pytest.mark.live


def _settings() -> Settings:
    """Свежий Settings из .env / окружения (не тестовый stub)."""
    return Settings()


def _has_gigachat() -> bool:
    return bool(_settings().gigachat_api_key.strip())


def _has_openrouter() -> bool:
    return bool(_settings().openrouter_api_key.strip())


requires_gigachat = pytest.mark.skipif(
    not _has_gigachat(),
    reason="GIGACHAT_API_KEY не задан — live LLM пропущен",
)
requires_openrouter = pytest.mark.skipif(
    not _has_openrouter(),
    reason="OPENROUTER_API_KEY не задан — live OpenRouter пропущен",
)


@requires_gigachat
async def test_live_gigachat_generate_short() -> None:
    """Короткий generate: ключ жив, SDK отдаёт непустой текст."""
    llm = GigaChatService(_settings())
    text = await llm.generate(
        [
            {
                "role": "user",
                "content": "Ответь одним словом: ок",
            }
        ]
    )
    assert text.strip()


@requires_gigachat
async def test_live_gigachat_embeddings_dim() -> None:
    """Эмбеддинг одного слова — размерность колонки chunks.embedding."""
    llm = GigaChatService(_settings())
    vectors = await llm.get_embeddings(["1С"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSIONS


@requires_gigachat
async def test_live_gigachat_classify_handoff_no() -> None:
    """Явный не-хэндофф → NO (дешёвый classify, не generate по 1С)."""
    llm = GigaChatService(_settings())
    result = await llm.classify_handoff(
        "Как провести поступление товаров в 1С?",
        system_prompt=HANDOFF_SYSTEM_PROMPT,
    )
    assert result is False


@requires_openrouter
async def test_live_openrouter_route_greeting() -> None:
    """Приветствие → greeting (или другой валидный intent без падения)."""
    classifier = OpenRouterClassifier(_settings())
    decision = await classifier.route("привет")
    assert decision["intent"] in {
        "greeting",
        "away",
        "offtopic",
        "handoff",
        "support",
    }


@requires_openrouter
async def test_live_openrouter_evaluate_case_good() -> None:
    """Нормальная пара вопрос/ответ → good или bad, но парсер не падает."""
    classifier = OpenRouterClassifier(_settings())
    verdict = await classifier.evaluate_case(
        question="Ошибка при проведении документа Поступление товаров",
        answer=(
            "Проверьте заполнение склада и контрагента, "
            "затем проведите документ заново."
        ),
    )
    assert verdict in {"good", "bad"}
