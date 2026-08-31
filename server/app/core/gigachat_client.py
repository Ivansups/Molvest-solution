"""Единый клиент GigaChat: генерация, Vision и эмбеддинги."""

import logging
from collections.abc import Sequence
from typing import Literal, TypedDict

from gigachat import GigaChat
from gigachat.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatContentPart,
    ChatMessage,
)

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

ChatRole = Literal["system", "user", "assistant"]

_DATA_URL_PREFIX = "data:image/png;base64,"


class ChatTurn(TypedDict):
    """Одно сообщение для генерации — без типов SDK."""

    role: ChatRole
    content: str


class GigaChatService:
    """Обёртка над SDK: авторизация и разбор ответа в одном месте."""

    def __init__(
        self,
        app_settings: Settings | None = None,
        client: GigaChat | None = None,
    ) -> None:
        self._settings = app_settings or settings
        self._client = client or GigaChat(
            credentials=self._settings.gigachat_api_key or None,
            base_url=self._settings.gigachat_api_url or None,
            model=self._settings.gigachat_model,
            scope=self._settings.gigachat_scope,
            verify_ssl_certs=self._settings.gigachat_verify_ssl_certs,
            timeout=self._settings.gigachat_timeout,
            max_retries=3,
        )

    async def generate(self, messages: Sequence[ChatTurn]) -> str:
        """Отправляет диалог в GigaChat и возвращает текст ответа."""
        chars = sum(len(turn["content"]) for turn in messages)
        logger.info(
            "GigaChat generate model=%s turns=%s chars=%s",
            self._settings.gigachat_model,
            len(messages),
            chars,
        )
        request = ChatCompletionRequest(messages=_to_messages(messages))
        response = await self._client.achat.create(request)
        text = _extract_text(response)
        logger.info("GigaChat generate готов chars=%s", len(text))
        return text

    async def chat_with_vision(self, image_base64: str, prompt: str) -> str:
        """Описывает скриншот через Vision. На вход — сырая base64-строка."""
        logger.info(
            "GigaChat vision model=%s image_chars=%s prompt_chars=%s",
            self._settings.gigachat_model,
            len(image_base64),
            len(prompt),
        )
        data_url = f"{_DATA_URL_PREFIX}{_strip_data_url_prefix(image_base64)}"
        image_part = ChatContentPart.model_validate(
            {"type": "image_url", "image_url": {"url": data_url}}
        )
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(
                    role="user",
                    content=[ChatContentPart(text=prompt), image_part],
                )
            ]
        )
        response = await self._client.achat.create(request)
        text = _extract_text(response)
        logger.info("GigaChat vision готов chars=%s", len(text))
        return text

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Векторизует тексты моделью эмбеддингов GigaChat."""
        logger.info(
            "GigaChat embeddings model=%s texts=%s chars=%s",
            self._settings.gigachat_embeddings_model,
            len(texts),
            sum(len(item) for item in texts),
        )
        result = await self._client.aembeddings(
            texts,
            model=self._settings.gigachat_embeddings_model,
        )
        logger.info("GigaChat embeddings готов vectors=%s", len(result.data))
        return [item.embedding for item in result.data]


def get_gigachat_service() -> GigaChatService:
    """Возвращает процесс-одиночку клиента."""
    return _service


def _to_messages(messages: Sequence[ChatTurn]) -> list[ChatMessage]:
    return [
        ChatMessage(
            role=turn["role"],
            content=[ChatContentPart(text=turn["content"])],
        )
        for turn in messages
    ]


def _extract_text(response: ChatCompletionResponse) -> str:
    if not response.messages:
        return ""
    parts = response.messages[0].content or []
    return "".join(part.text for part in parts if part.text)


def _strip_data_url_prefix(image_base64: str) -> str:
    marker = "base64,"
    if marker in image_base64:
        return image_base64.split(marker, 1)[1]
    return image_base64


_service = GigaChatService()
