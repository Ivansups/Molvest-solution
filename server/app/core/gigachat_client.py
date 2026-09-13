"""Единый клиент GigaChat: генерация, Vision и эмбеддинги."""

import asyncio
import base64
import logging
from collections.abc import Sequence
from typing import Literal, TypedDict

from gigachat import GigaChat
from gigachat.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatContentFile,
    ChatContentPart,
    ChatMessage,
)

from app.core.config import Settings, settings
from app.rag.chunking import estimate_tokens

logger = logging.getLogger(__name__)

ChatRole = Literal["system", "user", "assistant"]
# POST /embeddings принимает не только 514 токенов на элемент, но и бюджет
# токенов на весь запрос сразу («413 Request size exceeded» без номера
# элемента) — большой документ с полсотней чанков в одном вызове ловит его,
# даже если каждый чанк по отдельности укладывается в лимит. Бьём на пачки.
_EMBEDDINGS_BATCH_TOKEN_BUDGET = 8000
_EMBEDDINGS_BATCH_MAX_ITEMS = 32


class GigaChatError(Exception):
    """Ошибка обращения к GigaChat: сеть, SDK или неразборчивый ответ."""


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

    async def generate(
        self,
        messages: Sequence[ChatTurn],
        *,
        model: str | None = None,
    ) -> str:
        """Отправляет диалог в GigaChat и возвращает текст ответа."""
        chosen_model = model or self._settings.gigachat_model
        chars = sum(len(turn["content"]) for turn in messages)
        logger.info(
            "GigaChat generate model=%s turns=%s chars=%s",
            chosen_model,
            len(messages),
            chars,
        )
        if model is None:
            request = ChatCompletionRequest(messages=_to_messages(messages))
        else:
            request = ChatCompletionRequest(
                messages=_to_messages(messages),
                model=model,
            )
        response = await self._client.achat.create(request)
        text = _extract_text(response)
        logger.info("GigaChat generate готов chars=%s", len(text))
        return text

    async def classify_handoff(self, text: str, *, system_prompt: str) -> bool:
        """YES/NO классификация хэндоффа моделью Lite (`GigaChat-2`)."""
        model = self._settings.gigachat_classify_model
        timeout = self._settings.gigachat_classify_timeout
        logger.info(
            "GigaChat classify_handoff model=%s timeout=%s chars=%s",
            model,
            timeout,
            len(text),
        )
        try:
            content = await asyncio.wait_for(
                self.generate(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text},
                    ],
                    model=model,
                ),
                timeout=timeout,
            )
        except Exception as exc:
            logger.warning("GigaChat classify_handoff сбой: %s", exc)
            raise GigaChatError(str(exc)) from exc
        answer = content.strip().upper()
        if answer == "YES":
            return True
        if answer == "NO":
            return False
        logger.warning("GigaChat классификатор ответил неоднозначно: %r", content)
        raise GigaChatError(f"Неожиданный ответ классификатора: {content!r}")

    async def chat_with_vision(self, image_base64: str, prompt: str) -> str:
        """Описывает скриншот через Vision. На вход — сырая base64-строка."""
        model = self._settings.gigachat_vision_model
        logger.info(
            "GigaChat vision model=%s image_chars=%s prompt_chars=%s",
            model,
            len(image_base64),
            len(prompt),
        )
        payload = _strip_data_url_prefix(image_base64)
        mime = _image_mime(payload)
        filename = "screenshot.jpg" if mime == "image/jpeg" else "screenshot.png"
        uploaded = await self._client.aupload_file(
            (filename, base64.b64decode(payload), mime)
        )
        image_part = ChatContentPart(files=[ChatContentFile(id=uploaded.id_)])
        request = ChatCompletionRequest(
            model=model,
            messages=[
                ChatMessage(
                    role="user",
                    content=[ChatContentPart(text=prompt), image_part],
                )
            ],
        )
        response = await self._client.achat.create(request)
        text = _extract_text(response)
        logger.info("GigaChat vision готов chars=%s", len(text))
        return text

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Векторизует тексты моделью эмбеддингов GigaChat, пачками под лимит."""
        logger.info(
            "GigaChat embeddings model=%s texts=%s chars=%s",
            self._settings.gigachat_embeddings_model,
            len(texts),
            sum(len(item) for item in texts),
        )
        vectors: list[list[float]] = []
        for batch in _batch_by_token_budget(texts):
            result = await self._client.aembeddings(
                batch,
                model=self._settings.gigachat_embeddings_model,
            )
            vectors.extend(item.embedding for item in result.data)
        logger.info("GigaChat embeddings готов vectors=%s", len(vectors))
        return vectors


def get_gigachat_service() -> GigaChatService:
    """Возвращает процесс-одиночку клиента."""
    return _service


def _batch_by_token_budget(texts: list[str]) -> list[list[str]]:
    """Группирует тексты в пачки под лимит запроса /embeddings.

    Режет и по суммарной оценке токенов, и по числу элементов — что раньше
    упрётся в границу.
    """
    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for text in texts:
        tokens = estimate_tokens(text)
        if current and (
            current_tokens + tokens > _EMBEDDINGS_BATCH_TOKEN_BUDGET
            or len(current) >= _EMBEDDINGS_BATCH_MAX_ITEMS
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += tokens
    if current:
        batches.append(current)
    return batches


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


def _image_mime(payload: str) -> str:
    """MIME по сигнатуре: base64 JPEG всегда начинается с /9j/ (ff d8 ff).

    Клиент шлёт сжатый JPEG, старые скриншоты — PNG; на слово клиенту тут
    верить нельзя, а на эти два формата приходится всё, что доходит до Vision.
    """
    return "image/jpeg" if payload.startswith("/9j/") else "image/png"


_service = GigaChatService()
