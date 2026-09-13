"""Единый клиент OpenRouter: лёгкая LLM для маршрутизации запроса гостя.

Используется для intake-фильтра чата: решает, относится ли запрос к поддержке
(SUPPORT — дальше идёт RAG на GigaChat), просит ли гость оператора (HANDOFF —
эскалация) или это нерелевантный трафик (приветствие, проверка связи, оффтоп —
короткий ответ от малой модели без RAG). Генерацию ответов по 1С и эмбеддинги
по-прежнему делает GigaChat. Все вызовы OpenRouter — только через этот клиент,
не через сырой httpx в других местах.
"""

import logging
import re
from typing import Literal, TypedDict

import httpx

from app.agent.prompts import CASE_EVALUATION_PROMPT, ROUTER_SYSTEM_PROMPT
from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

_ROUTER_MAX_TOKENS = 256
_CASE_EVALUATION_MAX_TOKENS = 8

# Коды, которые малая модель возвращает первой строкой.
RouterIntent = Literal["greeting", "away", "offtopic", "handoff", "support"]
_ROUTER_INTENTS: dict[str, RouterIntent] = {
    "SUPPORT": "support",
    "HANDOFF": "handoff",
    "GREETING": "greeting",
    "AWAY_CHECK": "away",
    "OFFTOPIC": "offtopic",
}

# Вердикт по паре «вопрос — ответ» при пополнении базы знаний кейсами.
CaseEvaluation = Literal["good", "bad"]


class RouterDecision(TypedDict):
    """Решение intake-фильтра: маршрут запроса и (опционально) короткий ответ."""

    intent: RouterIntent
    reply: str


class OpenRouterError(Exception):
    """Ошибка обращения к OpenRouter: сеть, HTTP-код или неразборчивый ответ."""


def parse_router_decision(content: str) -> RouterDecision:
    """Разбирает ответ малой модели: код на первой строке, ответ — ниже.

    Неоднозначный ответ трактуется как ошибка: вызывающий код решает, как
    деградировать (фолбэк на GigaChat/правила), но никогда не считает мусор
    ответом по теме.
    """
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise OpenRouterError("Пустой ответ intake-фильтра")
    code = re.sub(r"[^A-Z_]", "", lines[0].upper())
    intent = _ROUTER_INTENTS.get(code)
    if intent is None:
        logger.warning("OpenRouter intake ответил неоднозначно: %r", content)
        raise OpenRouterError(f"Неожиданный ответ фильтра: {content!r}")
    reply = " ".join(lines[1:]).strip()
    logger.info("OpenRouter intake intent=%s reply=%s", intent, len(reply))
    return RouterDecision(intent=intent, reply=reply)


def parse_case_evaluation(content: str) -> CaseEvaluation:
    """Разбирает вердикт малой модели; всё, кроме точного GOOD/BAD, — ошибка.

    Fail-closed: неоднозначный ответ поднимает OpenRouterError, чтобы кейс не
    попал в базу знаний без явного подтверждения малой модели.
    """
    stripped = content.strip()
    if re.fullmatch(r"GOOD", stripped, re.IGNORECASE):
        return "good"
    if re.fullmatch(r"BAD", stripped, re.IGNORECASE):
        return "bad"
    logger.warning("OpenRouter оценка кейса неоднозначна: %r", content)
    raise OpenRouterError(f"Неожиданный вердикт кейса: {content!r}")


class OpenRouterClassifier:
    """Intake-роутер на лёгкой модели OpenRouter."""

    def __init__(
        self,
        app_settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = app_settings or settings
        self._client = client or httpx.AsyncClient(
            base_url=self._settings.openrouter_base_url,
            timeout=self._settings.openrouter_timeout,
            headers={
                "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )

    async def route(self, text: str) -> RouterDecision:
        """Классифицирует запрос и возвращает маршрут + короткий шаблон."""
        content = await self._complete(ROUTER_SYSTEM_PROMPT, text, _ROUTER_MAX_TOKENS)
        return parse_router_decision(content)

    async def evaluate_case(self, question: str, answer: str) -> CaseEvaluation:
        """Оценивает пару «вопрос — ответ» на пригодность для базы знаний."""
        content = await self._complete(
            CASE_EVALUATION_PROMPT,
            f"Вопрос: {question}\n\nОтвет: {answer}",
            _CASE_EVALUATION_MAX_TOKENS,
        )
        return parse_case_evaluation(content)

    def is_configured(self) -> bool:
        """Правда, если задан ключ — без него классификатор не вызываем."""
        return bool(self._settings.openrouter_api_key.strip())

    async def _complete(self, system_prompt: str, text: str, max_tokens: int) -> str:
        """Один запрос к chat/completions; возвращает сырой текст ответа."""
        logger.info(
            "OpenRouter complete model=%s text_chars=%s",
            self._settings.openrouter_model,
            len(text),
        )
        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            logger.warning("OpenRouter complete сеть: %s", exc)
            raise OpenRouterError(str(exc)) from exc
        if response.status_code != 200:
            logger.warning(
                "OpenRouter complete HTTP %s: %s",
                response.status_code,
                response.text[:200],
            )
            raise OpenRouterError(f"HTTP {response.status_code}")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning(
                "OpenRouter complete ответ без контента: %s", response.text[:200]
            )
            raise OpenRouterError("Нет контента в ответе") from exc
        return content if isinstance(content, str) else str(content)


def get_openrouter_classifier() -> OpenRouterClassifier:
    """Возвращает процесс-одиночку классификатора."""
    return _classifier


_classifier = OpenRouterClassifier()
