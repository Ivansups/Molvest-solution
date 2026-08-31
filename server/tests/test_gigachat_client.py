"""Юнит-тесты обёртки GigaChat — без реальных вызовов API."""

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
from app.core.gigachat_client import GigaChatService


def _chat_response(text: str) -> ChatCompletionResponse:
    return ChatCompletionResponse(
        messages=[ChatMessage(role="assistant", content=[ChatContentPart(text=text)])]
    )


def _service(
    *,
    embeddings_model: str = "Embeddings",
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
    )
    return GigaChatService(settings, client=cast(GigaChat, client)), client


async def test_generate_extracts_text() -> None:
    service, client = _service()
    text = await service.generate([{"role": "user", "content": "привет"}])
    assert text == "ok"
    client.achat.create.assert_awaited_once()


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


@pytest.mark.parametrize("model", ["Embeddings", "Embeddings-2"])
async def test_get_embeddings_uses_model_from_settings(model: str) -> None:
    service, client = _service(embeddings_model=model)
    vectors = await service.get_embeddings(["документ"])
    assert vectors == [[0.1, 0.2]]
    client.aembeddings.assert_awaited_once_with(["документ"], model=model)


def test_embeddings_model_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(gigachat_embeddings_model="  ")
