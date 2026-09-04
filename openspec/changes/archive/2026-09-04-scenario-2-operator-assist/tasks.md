## 1. Схема и конфиг

- [x] 1.1 Добавить `OPERATOR_ASSIST_MODE` (`draft` | `auto`, дефолт `draft`) в `Settings` и `.env.example`
- [x] 1.2 Alembic: nullable `conversations.suggested_response` (Text); расширить `MessageRole` значением `operator`
- [x] 1.3 `GET /api/conversations/{id}` отдаёт `suggested_response`; `uv run alembic check`

## 2. Граф

- [x] 2.1 Передавать `conversation_status` в state из `run_chat_turn`; граф без своей сессии БД
- [x] 2.2 На `open` слабый скор по-прежнему без generate; retrieve нужен только чтобы решить эскалацию
- [x] 2.3 В `draft` на уже `escalated` не читать кэш, не retrieve, не generate
- [x] 2.4 Тесты: слабый скор на `open` без generate; повтор на `open` из кэша; `draft`+`escalated` — ни retrieve, ни generate

## 3. Persist хода

- [x] 3.1 Первая эскалация: system-фраза гостю, строка Escalation, `suggested_response` пустой
- [x] 3.2 Повторный ход в `draft` на `escalated`: только user message, черновик не трогаем, без LLM
- [x] 3.3 `auto` на `escalated` при скоре ≥ порога: assistant гостю, статус остаётся `escalated`
- [x] 3.4 `POST /chat` на `resolved` → 409, сообщений нет; идемпотентная эскалация по-прежнему одна строка

## 4. API оператора

- [x] 4.1 `POST /api/conversations/{id}/messages` (`installation_id`, `text`): роль `operator`, чистит черновик; не `escalated` → 409; чужая установка → 404
- [x] 4.2 `POST /api/conversations/{id}/resolve`: `transition_status(escalated→resolved)`, `resolved_at`, чистит черновик; повтор → 200
- [x] 4.3 `POST /api/conversations/{id}/suggest`: граф по последнему сообщению гостя, только `suggested_response`; не `escalated` / нет user-сообщения → 409; лента и статус не меняются
- [x] 4.4 Тесты: ответ, suggest, 409 на open, повтор resolve, internal token как на остальных `/api/conversations`

## 5. Консоль оператора

- [x] 5.1 `chatService`: список с `status=escalated`, маппинг `suggested_response`, `generateSuggestion`, `sendOperatorReply`, `resolveConversation`
- [x] 5.2 `/operator` и support-чат: живые эскалации, панель черновика, кнопка «Сгенерировать ответ» с loading, `refetchInterval` 5 с; не вызывать `/api/operator/tickets`
- [x] 5.3 Generate → suggest API; отправка → messages API; resolved → resolve API; ни одно из трёх не идёт в `POST /chat`
- [x] 5.4 `pnpm --dir frontend lint && pnpm --dir frontend typecheck`

## 6. Гостевой чат

- [x] 6.1 После `conversation_id` поллить детали раз в 5 с и дописывать `operator` / новые `assistant`
- [x] 6.2 Не показывать `suggested_response` в ленте гостя
- [x] 6.3 Обновить `docs/TESTS.md`: сценарий 2 закрыт API+графом; UI по-прежнему без Playwright

## 7. Quality gate

- [x] 7.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- [x] 7.2 `cd server && uv run pytest`
- [x] 7.3 `pnpm --dir frontend lint && pnpm --dir frontend typecheck`
