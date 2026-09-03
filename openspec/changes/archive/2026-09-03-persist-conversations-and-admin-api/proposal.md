## Why

`POST /chat` не пишет строки в БД: диалоги, сообщения и эскалации нигде не персистятся. Из-за этого флаг `escalated` в JSON не сопровождается записью `Escalation`, и админка этапа 6 (логи диалогов и метрики) смотрит в пустоту. Нужно замкнуть RAG с хранилищем диалогов и отдать данные наружу read-only ручками.

## What Changes

- **Persist**: `POST /chat` создаёт/обновляет `Conversation`, пишет `Message` (user и assistant/system) в одной транзакции. Сохраняются `confidence`, `sources`, признак эскалации.
- **Эскалация**: при `escalated=true` статус меняется только через `transition_status` (open → escalated), создаётся строка `Escalation` (conversation_id, message_id, reason, escalated_to), в ответе — непустой текст гостю про передачу оператору. Повтор того же хода не создаёт вторую эскалацию; статус `escalated` не сбрасывается.
- **Read-only API этапа 6**: `GET /api/conversations` (пагинация, фильтры дата/user/status, в т.ч. `escalated`), `GET /api/conversations/{id}` (сообщения, confidence, sources), `GET /api/metrics` (% автоответов, среднее время ответа, число эскалаций). НЕ добавляем `/api/operator/tickets`, `/api/analytics`, `/api/settings`, `/api/dashboard`.
- Снимается ограничение OpenAPI: `test_openapi_documents.py` больше не запрещает `/api/conversations`.

## Capabilities

### New Capabilities
- `conversation-api`: (внутри изменённой `conversation-records`) — read-only получение диалогов и агрегированных метрик для админки этапа 6.

### Modified Capabilities
- `conversation-records`: `POST /chat` теперь обязан персистить Conversation/Message; эскалация обязана создавать строку Escalation через `transition_status`; убирается требование «No public conversation API» и добавляется read-only API диалогов/метрик.

## Impact

- `server/app/services/agent.py` — `run_chat_turn` сохраняет диалог и сообщения; сервис эскалации.
- `server/app/api/chat.py` — корректный гостевой текст при эскалации.
- `server/app/selectors/` — новые селекторы диалогов и метрик.
- `server/app/api/` — роутеры `/api/conversations` и `/api/metrics`.
- `server/tests/test_openapi_documents.py` — снятие запрета на conversations.
- Миграции не требуются: таблицы Conversation/Message/Escalation уже созданы (этап 2). Возможна только новая Alembic-ревью, если понадобятся индексы для фильтров/метрик.
