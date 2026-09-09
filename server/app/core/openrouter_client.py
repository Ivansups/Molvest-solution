"""Единый клиент OpenRouter: лёгкая LLM для классификации запроса гостя.

Используется только для детекта хэндоффа (просьбы передать диалог человеку):
ответы и эмбеддинги по-прежнему делает GigaChat. Все вызовы OpenRouter —
только через этот клиент, не через сырой httpx в других местах.
"""

import logging

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

# Промпт-классификатор: строгий ответ одной меткой, без пояснений.
_HANDOFF_SYSTEM_PROMPT = (
    "Ты классификатор запросов техподдержки ПО 1С. Отвечай строго ОДНИМ словом: "
    "YES если пользователь просит передать диалог живому человеку "
    "(позвать/вызвать/соединить/передать оператору или специалисту, «нужен человек», "
    "«хочу поговорить с человеком») — или NO во всех остальных случаях. "
    "Вопрос «как позвать оператора в 1С», «что делает оператор» — это НЕ просьба, "
    "отвечай NO. Никакого текста кроме YES или NO."
)

_MAX_TOKENS = 5


class OpenRouterError(Exception):
    """Ошибка обращения к OpenRouter: сеть, HTTP-код или неразборчивый ответ."""


class OpenRouterClassifier:
    """Классификатор хэндоффа на лёгкой модели OpenRouter."""

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

    async def is_handoff_request(self, text: str) -> bool:
        """Правда, если пользователь просит передать диалог человеку."""
        content = await self._classify(text)
        answer = content.strip().upper()
        if answer == "YES":
            return True
        if answer == "NO":
            return False
        logger.warning("OpenRouter классификатор ответил неоднозначно: %r", content)
        raise OpenRouterError(f"Неожиданный ответ классификатора: {content!r}")

    def is_configured(self) -> bool:
        """Правда, если задан ключ — без него классификатор не вызываем."""
        return bool(self._settings.openrouter_api_key.strip())

    async def _classify(self, text: str) -> str:
        """Один запрос на классификацию; возвращает сырой текст ответа модели."""
        logger.info(
            "OpenRouter classify model=%s text_chars=%s",
            self._settings.openrouter_model,
            len(text),
        )
        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": _HANDOFF_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "max_tokens": _MAX_TOKENS,
            "temperature": 0,
        }
        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            logger.warning("OpenRouter classify сеть: %s", exc)
            raise OpenRouterError(str(exc)) from exc
        if response.status_code != 200:
            logger.warning(
                "OpenRouter classify HTTP %s: %s",
                response.status_code,
                response.text[:200],
            )
            raise OpenRouterError(f"HTTP {response.status_code}")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning(
                "OpenRouter classify ответ без контента: %s", response.text[:200]
            )
            raise OpenRouterError("Нет контента в ответе") from exc
        return content if isinstance(content, str) else str(content)


def get_openrouter_classifier() -> OpenRouterClassifier:
    """Возвращает процесс-одиночку классификатора."""
    return _classifier


_classifier = OpenRouterClassifier()
