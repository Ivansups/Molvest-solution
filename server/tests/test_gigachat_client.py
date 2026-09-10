"""Юнит-тесты обёртки GigaChat — без реальных вызовов API."""

import asyncio
import base64
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from gigachat import GigaChat
from gigachat.models import (
    ChatCompletionResponse,
    ChatContentPart,
    ChatMessage,
)
from pydantic import ValidationError

from app.core.config import Settings
from app.core.gigachat_client import GigaChatError, GigaChatService


def _chat_response(text: str) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        messages=[ChatMessage(role="assistant", content=[ChatContentPart(text=text)])]
    )


def _service(
    *,
    embeddings_model: str = "Embeddings",
    classify_timeout: float = 8.0,
) -> tuple[GigaChatService, MagicMock]:
    client = MagicMock()
    client.achat.create = AsyncMock(return_value=_chat_response("ok"))
    embedding_item = MagicMock()
    embedding_item.embedding = [0.1, 0.2]
    embeddings = MagicMock()
    embeddings.data = [embedding_item]
    client.aembeddings = AsyncMock(return_value=embeddings)
    settings = Settings(
        gigachat_api_key="test-key",
        gigachat_model="GigaChat-2",
        gigachat_embeddings_model=embeddings_model,
        gigachat_classify_timeout=classify_timeout,
    )
    return GigaChatService(settings, client=cast(GigaChat, client)), client


async def test_generate_extracts_text() -> None:
    service, client = _service()
    text = await service.generate([{"role": "user", "content": "привет"}])
    assert text == "ok"
    client.achat.create.assert_awaited_once()
    request = client.achat.create.await_args.args[0]
    assert request.model is None


async def test_classify_handoff_yes() -> None:
    service, client = _service()
    client.achat.create = AsyncMock(return_value=_chat_response("YES"))
    assert (
        await service.classify_handoff("позовите оператора", system_prompt="p") is True
    )
    request = client.achat.create.await_args.args[0]
    assert request.model == "GigaChat-2"


async def test_classify_handoff_rejects_garbage() -> None:
    service, client = _service()
    client.achat.create = AsyncMock(return_value=_chat_response("может быть"))
    with pytest.raises(GigaChatError, match="Неожиданный ответ"):
        await service.classify_handoff("позовите оператора", system_prompt="p")


async def test_classify_handoff_times_out() -> None:
    service, client = _service(classify_timeout=0.05)

    async def _slow(*_args: object, **_kwargs: object) -> ChatCompletionResponse:
        await asyncio.sleep(1)
        return _chat_response("YES")

    client.achat.create = _slow
    with pytest.raises(GigaChatError):
        await service.classify_handoff("позовите оператора", system_prompt="p")


async def test_chat_with_vision_adds_data_url_prefix() -> None:
    service, client = _service()
    await service.chat_with_vision("iVBORw0KGgo", "опиши")
    request = client.achat.create.await_args.args[0]
    image_part = request.messages[0].content[1]
    extra = image_part.model_dump()
    assert extra["image_url"]["url"] == "data:image/png;base64,iVBORw0KGgo"


async def test_chat_with_vision_strips_existing_prefix() -> None:
    service, client = _service()
    await service.chat_with_vision("data:image/png;base64,ABC", "опиши")
    request = client.achat.create.await_args.args[0]
    image_part = request.messages[0].content[1]
    assert image_part.model_dump()["image_url"]["url"] == ("data:image/png;base64,ABC")


async def test_chat_with_vision_detects_jpeg() -> None:
    """Клиент сжимает скриншоты в JPEG — MIME берём из сигнатуры, не хардкодим."""
    service, client = _service()
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01").decode()
    await service.chat_with_vision(jpeg, "опиши")
    request = client.achat.create.await_args.args[0]
    image_part = request.messages[0].content[1]
    assert image_part.model_dump()["image_url"]["url"].startswith("data:image/jpeg;")


@pytest.mark.parametrize("model", ["Embeddings", "Embeddings-2"])
async def test_get_embeddings_uses_model_from_settings(model: str) -> None:
    service, client = _service(embeddings_model=model)
    vectors = await service.get_embeddings(["документ"])
    assert vectors == [[0.1, 0.2]]
    client.aembeddings.assert_awaited_once_with(["документ"], model=model)


def test_embeddings_model_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(gigachat_embeddings_model="  ")
