## Context

Сценарий 2 ТЗ требует пассивного подключения агента к живому треду Bitrix «пользователь ↔ оператор»: агент слушает тред, готовит оператору черновик (`draft`) или отвечает пользователю сам (`auto`). В коде входящего адаптера Bitrix нет (`channels/` отсутствует), поэтому вместе с live-assist вводится импровизированный `POST /webhook/bitrix` (внутренний таск №26).

Базой является консольный сценарий 2: `POST /api/conversations/{id}/suggest` (`services/operator.py`), `Conversation.suggested_response`, runtime-режим `draft`/`auto` (`services/runtime_settings.py`), общий RAG-граф (`services/agent.py` → `run_chat_turn`).

## Goals / Non-Goals

**Goals:**

- Вебхук принимает события живого треда: `workspace_id`, `thread_id`, `message_id`, `sender` (`user` | `operator`), текст, опциональный `user_id`.
- Маппинг `(channel, thread_id, installation_id) → conversation_id`; первый пользовательский ход создаёт диалог, остальные продолжают его.
- Идемпотентность: повтор события с тем же `(channel, message_id)` не пишет дубль, не запускает граф и отвечает `duplicate`.
- draft: на ход пользователя — retrieve + generate → `suggested_response` оператору, ответ пользователю не уходит, статус не меняется.
- auto: полный граф сценария 1; высокий confidence → ответ пользователю, низкий → эскалация.
- Сообщение оператора пишется в ленту без запуска графа, черновик не трогает.
- Режим и порог — из runtime-настроек на каждое событие (смена без рестарта).

**Non-Goals:**

- Реальный REST Bitrix (autoinvite, методы приложения), Redmine, SSE, обучение на кейсах, фронтенд.
- Поллинг/подписка Bitrix — только импровизированный вебхук.

## Decisions

### D1. Контракт вебхука и аутентификация

`POST /webhook/bitrix`, тело — `BitrixWebhookEvent`:

```
workspace_id: str
thread_id: str
message_id: str
sender: Literal["user", "operator"]
text: str | None = None
user_id: str | None = None
```

Ответ — `BitrixWebhookResponse`:

```
conversation_id: UUID
status: Literal["processed", "duplicate"]
draft: str | None   # draft-режим: черновик оператору
reply: str | None   # auto-режим: текст ответа пользователю
escalated: bool
```

Роутер защищён `require_internal_token` (заголовок `X-Internal-Token`), как остальные `/api/*`. Некорректный `sender` → 422, ничего не пишется. `installation_id = workspace_to_installation_id(workspace_id)` (тот же детерминированный uuid5, что в `POST /chat`).

### D2. Маппинг тредов — таблица `channel_threads`

Новая модель `ChannelThread`:

- `channel` (str «bitrix»), `thread_id`, `installation_id`, `conversation_id` (FK → `conversations.id`, `ondelete=CASCADE`), `created_at`.
- Уникальный ключ `uq_channel_threads_channel_thread_installation` на `(channel, thread_id, installation_id)`: тред другой установки получает свой диалог (spec «Same thread id in another installation»).
- Индекс `ix_channel_threads_conversation_id` — для поиска по диалогу.
- Relationship на диалог не нужен: достаточно колонки `conversation_id` — читаем `session.get(Conversation, row.conversation_id)`.

Поиск: `SELECT ... WHERE channel=? AND thread_id=? AND installation_id=?`. Не найдено → создаём `Conversation(open)` и маппинг при первом пользовательском ходе (в auto — маппинг после `persist_turn`, когда у диалога уже есть id).

### D3. Идемпотентность — колонки на `messages`, не отдельная таблица

Добавляем на `messages` nullable-колонки `channel` и `channel_message_id` + уникальный индекс `uq_messages_channel_message_id` на `(channel, channel_message_id)`. Это одновременно реестр обработанных событий и источник провенанса. Агентные сообщения (`assistant`/`system`) пишутся с NULL в обеих колонках — Postgres к уникальности NULL не приводит к конфликтам.

Обработка: ранний `SELECT Message WHERE channel=? AND channel_message_id=?` → найден → ответ `duplicate` без персиста, без графа, без черновика/эскалации. Повтор `user` в auto и повтор `operator` покрываются тем же запросом.

### D4. Сообщение оператора — пассивная запись

Событие `operator` пишет `Message(role=operator, content=text)` с канальными полями и коммитится. Граф не запускается. Черновик **не трогается** (в отличие от консольного `add_operator_reply`, который чистит `suggested_response` и требует `escalated` — здесь он не используется).

### D5. Draft-режим — общий retrieve+generate

На сообщение пользователя:

1. Персистим `Message(role=user)` с канальными полями, создаём/продолжаем маппинг, коммит.
2. Вызываем общий helper `generate_draft(session, conversation=..., query=text)` из нового `services/draft.py`: история (`list_recent_messages`), `make_retriever` + `generate` — ровно те узлы, что сейчас в `generate_suggestion`.
3. Ответ пишется только в `conversation.suggested_response`, коммит. Статус не меняется (низкий confidence не эскалирует — spec «Draft does not escalate»), транскрипт не пополняется assistant-сообщением.
4. Возвращаем `status=processed`, `draft=<текст>`.

`generate_suggestion` рефакторится на этот же helper (внутренняя логика выносится, guard «только escalated» остаётся в `operator.py`).

### D6. Auto-режим — переиспользование `run_chat_turn`

Auto не дублирует граф: `live_thread` строит `ChatRequest` (детерминированный uuid5 от `message_id` для поля `message_id`, `text` из события, `conversation_id` из маппинга или `None` для нового треда) и вызывает `run_chat_turn(request, session, channel="bitrix", channel_message_id=event.message_id)`. Проброс `channel`/`channel_message_id` добавляется в `add_user_message`/`persist_guest_hold`/`persist_turn`, чтобы персистнутое user-сообщение несло канальные поля (D3).

Решение из `ChatResponse`:

- `escalated=True` → `reply=None`, `escalated=True` (фраза гостя + `Escalation` уже записаны `persist_turn`).
- `escalated=False` → `reply=text`.

`run_chat_turn` сам создаёт диалог для нового треда (`conversation_id=None`) и переводит `open→escalated` при низком confidence. Статус меняется только через `transition_status`.

### D7. Закрытый диалог в треде

Маппинг ведёт на `resolved` диалог → `run_chat_turn` бросит `ConversationConflictError` («Диалог уже закрыт»), вебхук отвечает 409. То же поведение, что и `POST /chat` на `resolved`: закрытый диалог ходов не принимает.

### D8. Режим и порог — из runtime-настроек на каждое событие

`live_thread` вызывает `get_effective_operator_assist_mode()` и `get_effective_confidence_threshold()` при обработке каждого события (для draft-эскалации-нет; для auto порог применяется в графе). Тест смены режима: `update_effective_settings(draft→auto)` без рестарта, затем новое сообщение — обрабатывается как auto.

## Risks / Trade-offs

- [Одновременный повтор одного события] → ранний SELECT не успевает, но уникальный индекс `uq_messages_channel_message_id` не даст дубля строки. Для демо достаточен SELECT-first; дополнительный catch не добавляем.
- [Сообщение в resolved-тред уходит в 409] → консистентно с `POST /chat`; импровизированный вебхук шлёт событие один раз.
- [Черновик появляется только после хода пользователя] → это и есть draft-ассистент; оператор видит подсказку сразу в треде и в консоли-зеркале.
- [Два первых события нового треда могут создать два диалога] → маловероятно и не конфликтует (маппинг перезапишется последним); вне объёма.

## Migration Plan

1. Alembic `003_channel_threads`: таблица `channel_threads` + колонки `messages.channel`, `messages.channel_message_id` + `uq_messages_channel_message_id`. Импорты в `app/models/__init__.py` и `tests/conftest.py` (иначе `Base.metadata.create_all` не создаст таблицу в тестах).
2. `services/draft.py` + рефакторинг `generate_suggestion`.
3. `channels/bitrix/` (schemas + webhook-роутер), `services/live_thread.py`, проброс канала в `run_chat_turn`/persist.
4. Регистрация роутера в `main.py`, тесты, quality gate.
5. Откат: `downgrade` миграции, удаление вебхука из `main.py`.

## Open Questions

Нет. Режим по умолчанию `draft` (env `OPERATOR_ASSIST_MODE`), как в сценарии 2.