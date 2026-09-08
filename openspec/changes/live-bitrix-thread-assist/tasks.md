## 1. Схема и миграция

- [x] 1.1 `ChannelThread` в `app/models/channel.py`: `channel`, `thread_id`, `installation_id`, `conversation_id` (FK, `ondelete=CASCADE`), `created_at`; `uq_channel_threads_channel_thread_installation`, `ix_channel_threads_conversation_id`
- [x] 1.2 `Message`: nullable `channel`, `channel_message_id` + `uq_messages_channel_message_id`; регистрация в `app/models/__init__.py` и импорте моделей в `tests/conftest.py`
- [x] 1.3 Alembic `003_channel_threads` (up/down); `cd server && uv run alembic check`

## 2. Общий черновик

- [x] 2.1 `app/services/draft.py` `generate_draft(session, *, conversation, query) -> str | None`: `list_recent_messages` → `make_retriever` → `generate`, без guard на статус и без записи
- [x] 2.2 `generate_suggestion` в `operator.py` использует `generate_draft`; тесты `test_operator_api.py` зелёные (guard «только escalated» сохраняется)

## 3. Проброс канала в персист

- [x] 3.1 `add_user_message`, `persist_guest_hold`, `persist_turn` принимают `channel`/`channel_message_id` и кладут их в `Message`
- [x] 3.2 `run_chat_turn(request, session, *, channel=None, channel_message_id=None)`; тест: повторный вызов графа не нужен, `pytest` зелёный

## 4. Webhook Bitrix

- [x] 4.1 `app/channels/bitrix/schemas.py`: `BitrixWebhookEvent` (`workspace_id`, `thread_id`, `message_id`, `sender: Literal["user","operator"]`, `text`, `user_id`), `BitrixWebhookResponse` (`conversation_id`, `status`, `draft`, `reply`, `escalated`)
- [x] 4.2 `app/channels/bitrix/webhook.py`: `POST /webhook/bitrix` с `require_internal_token`; invalid sender → 422; делегирует в `services/live_thread`
- [x] 4.3 Регистрация роутера в `app/main.py`; `/webhook/bitrix` в OpenAPI

## 5. Live-тред сервис

- [x] 5.1 Дубль: `SELECT Message WHERE channel=? AND channel_message_id=?` → ранний `duplicate` без графа/персиста
- [x] 5.2 Маппинг `(channel, thread_id, installation_id)` → conversation; первый ход создаёт `open`, чужая установка — свой диалог
- [x] 5.3 Событие `operator`: только `Message(role=operator)` с канальными полями; граф не запускается, черновик не меняется
- [x] 5.4 `draft`: user-сообщение + `generate_draft` → `suggested_response`; статус не меняется (низкий confidence не эскалирует); в ответе `draft`
- [x] 5.5 `auto`: `run_chat_turn` с канальными полями; `escalated` → `escalated=True`, иначе `reply=text`; маппинг создаётся после персиста; режим/порог из `get_effective_*`
- [x] 5.6 Маппинг на `resolved` → 409 (как `POST /chat`)

## 6. Тесты

- [x] 6.1 `test_bitrix_webhook.py`: первый user-ход создаёт conversation + маппинг; дубль → `duplicate` и без повтора графа (monkeypatch счётчик)
- [x] 6.2 draft: черновик в `suggested_response` и ответе, нет assistant-сообщения, статус не escalated даже при низком confidence
- [x] 6.3 auto: уверенность ≥ порога → `reply`, assistant-сообщение; ниже порога → `escalated=True`, строка Escalation, фраза гостя, без `reply`
- [x] 6.4 operator: роль `operator` в диалоге, черновик не тронут, граф не вызван; дубль operator-события — одно операторское сообщение в транскрипте
- [x] 6.5 Смена режима через `update_effective_settings` без рестарта; одинаковый `thread_id` в другой установке → свой диалог; invalid sender → 422
- [x] 6.6 Без `X-Internal-Token` → 401 (monkeypatch `settings.internal_service_token`)

## 7. Quality gate

- [x] 7.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- [x] 7.2 `cd server && uv run pytest`
- [x] 7.3 `cd server && uv run alembic check`