## Context

См. proposal.md — Why. Сейчас граф LangGraph (`server/app/agent/graph.py`) вычисляет `escalated`/`confidence`/`answer`, но `services/agent.run_chat_turn` только мапит состояние в `ChatResponse` и ничего не персистит. Таблицы `conversations`/`messages`/`escalations` и сервис `services/conversation_status.transition_status` уже созданы (этап 2) и покрыты тестами, но в проде не используются. Read-only API диалогов и метрик отсутствует.

Граф намеренно не знает о БД (каналовая/агентная изоляция) — persist должен происходить на уровне сервиса, который владеет и графом, и сессией БД.

## Goals / Non-Goals

**Goals:**
- Персистить каждый ход `POST /chat` в `Conversation`/`Message` одной транзакцией.
- При слабом скоре эскалировать через `transition_status` и создавать `Escalation`; не дублировать при повторе.
- Дать read-only API: список диалогов с фильтрами, детали, метрики.
- Сохранить контракт `POST /chat` обратно-совместимым.

**Non-Goals:**
- Ответ оператора в том же виджете (эскалация read-only для гостя).
- Bitrix / SSE / tRPC / обучение на кейсах.
- Эндпоинты `/api/operator/tickets`, `/api/analytics`, `/api/settings`, `/api/dashboard`.

## Decisions

### D1. Persist на уровне сервиса, не в графе

`run_chat_turn` получает `AsyncSession` и после `ainvoke` пишет пользовательское и ассистентское сообщения. Граф остаётся чистым от БД. Это соответствует AGENTS.md: изменение состояния — в `services/`, а не в узлах.

- Альтернатива (писать в узле графа) — отвергнута: ломает изоляцию агентного слоя и тестовую подмену графа.
- `run_chat_turn` принимает `session` как параметр; роутер `POST /chat` прокидывает зависимую сессию.

### D2. Определение conversation_id

Если `request.conversation_id` задан — используем существующий диалог; иначе создаём новый `Conversation` (status `open`). Ответ всегда возвращает актуальный `conversation_id` (для нового — созданный UUID).

### D3. Сообщения и роль ассистента при эскалации

- user-сообщение пишется всегда.
- Если граф дал `escalated=true` (answer пустой) — пишем одно ассистентское (`system`) сообщение с гостевой фразой «Передано оператору» и `escalated=True`.
- Иначе пишем ассистентское (`assistant`) сообщение с реальным `answer`, `confidence` и `sources`.
- Каноническая гостяная фраза — константа в сервисе.

### D4. Эскалация идемпотентна

Сервис эскалации: если `conversation.status` ещё `open` — вызвать `transition_status(open→escalated)` и создать `Escalation`; если уже `escalated` — не создавать вторую строку и не менять статус. Это обеспечивает «повтор хода не создаёт вторую эскалацию» и «не даунгрейд эскалированного».

### D5. Транзакционность

Смена статуса + создание `Escalation` + запись сообщений — в одной транзакции (одна сессия, один commit). При ошибке всё откатывается вместе (AGENTS.md: изменение состояния + audit — в одной transaction).

### D6. Metric изменения — без миграции

`conversations.created_at` и `messages.created_at` уже есть; % автоответов и среднее время считаем из `Message` (роли/confidence/escalated). Число эскалаций — из `Escalation`. Отдельная миграция не нужна; при необходимости тестов — фикстура создаёт строки.

### D7. Read-only селекторы и роутеры

По AGENTS.md: чтение — `selectors/`, изменение — `services/`. Новые файлы:
- `selectors/conversations.py` — список (date/user/status фильтры + пагинация), детали, агрегаты метрик.
- `api/conversations.py` — `GET /api/conversations`, `GET /api/conversations/{id}`.
- `api/metrics.py` — `GET /api/metrics`.
- `schemas/conversations.py`, `schemas/metrics.py` — Pydantic.

Не добавляются `/api/operator/tickets`, `/api/analytics`, `/api/settings`, `/api/dashboard`.

## Risks / Trade-offs

- [Граф не пишет в БД → если добавится persist-логика в узлах позднее, будет два источника] → фиксируем правило: только `services/`, узел — вычислительный.
- [Повторный ход одного слабого вопроса мог бы «переаппендить» сообщения] → диалог один, user/assistant message добавляются как новые строки; эскалация идемпотентна по статусу.
- [Метрики по вставкам, а не по времени-персиста] → считаем от `created_at` сообщений; если понадобится время обработки — добавим в сообщение поле в отдельном тикете (вне scope).
- [Изменение существующей spec conversation-records] → delta-файл + архив при сдаче.

## Migration Plan

Деплой: применяется поверх существующей схемы (таблицы уже есть). Миграция не требуется для persist/API. Если метрики потребуют индексов по `messages.created_at` / `conversations.status` — добавить Alembic-ревью в этом же change (сейчас таких индексов нет, на объёме хакатона не критично).

## Open Questions

- Формат `date`-фильтра (ISO дата, с таймзоной) — решит реализация по умолчанию как `created_at >=`/`<=`; на контракт API это не влияет.
