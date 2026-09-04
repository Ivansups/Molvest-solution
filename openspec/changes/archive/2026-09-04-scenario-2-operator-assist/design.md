## Context

Сценарий 2: агент помогает оператору черновиком, не отвечает гостю сам (пока включён `draft`). Сейчас после эскалации нет ни черновика, ни ответа оператора, ни resolve.

Дорогая часть GigaChat — `generate`. Поэтому гостевой ход её не вызывает: ни при первой эскалации, ни при каждом следующем сообщении. Модель дергается только с кнопки «Сгенерировать ответ».

Канал для демо — веб-виджет. Триггер сценария 2 — статус `escalated`.

## Goals / Non-Goals

**Goals:**

- Эскалация без generate, как сейчас: гостю фраза, оператору тикет с пустым черновиком.
- Follow-up гостя в `draft` на `escalated`: сохранить сообщение, не вызывать retrieve/generate.
- Оператор по кнопке считает черновик (retrieve + generate), правит, отправляет, закрывает тикет.
- Гость видит ответы оператора без перезагрузки.
- Статус только через `transition_status`. Граф без сессии БД.

**Non-Goals:**

- Авточерновик на каждое сообщение гостя.
- Bitrix/Redmine, SSE, API настроек, `/api/operator/tickets`, обучение на кейсах.

## Decisions

### D1. Сценарий 2 включается статусом `escalated`

Пока `open` — сценарий 1. После `escalated` гостевой `POST /chat` не автоответчик.

### D2. Режим — env `OPERATOR_ASSIST_MODE`, по умолчанию `draft`

| Состояние | Режим | Гостю | GigaChat generate |
| --- | --- | --- | --- |
| `open`, скор ≥ порога | любой | ответ модели | да |
| `open`, скор < порога | любой | фраза эскалации | нет |
| `escalated` | `draft` | фраза ожидания | нет, пока оператор не нажмёт кнопку |
| `escalated` | `auto`, скор ≥ порога | ответ модели | да |
| `escalated` | `auto`, скор < порога | как draft | нет |

`auto` оставляем для сценария «агент встроен в диалог». Демо и экономия токенов — `draft`.

### D3. Гостевой ход в draft не ходит в LLM

На `open` слабый скор: retrieve нужен, чтобы решить эскалировать; generate **нет** (`_after_retrieve` как сейчас).

На уже `escalated` + `draft`: не читаем кэш ответа, не retrieve, не generate. Сервис пишет user message и возвращает фразу ожидания.

`run_chat_turn` передаёт `conversation_status` в state.

### D4. Черновик — колонка `conversations.suggested_response`

Nullable Text. Пустая после эскалации, пока оператор не вызвал suggest. Не Message. После ответа оператора и resolve — NULL.

### D5. Роль `operator` без native enum

`POST /api/conversations/{id}/messages` только на `escalated`, иначе 409. Граф не запускается.

`POST /api/conversations/{id}/resolve`: `escalated → resolved`, `resolved_at`, черновик NULL. Повтор — 200.

Список тикетов = `GET /api/conversations?status=escalated`.

### D6. Кнопка — единственный generate для черновика

«Сгенерировать ответ» → `POST /api/conversations/{id}/suggest`. Только `escalated`. Берёт последнее сообщение гостя и историю. Retrieve + generate. Пишет только `suggested_response`. Ленту и статус не трогает. Нет user-сообщения → 409. Повтор кнопки перезаписывает черновик.

Не `POST /chat`: иначе появилась бы фейковая реплика гостя.

Кнопка в loading до ответа (таймаут как у Vision, ≥ 60 с). Старый черновик на экране, пока не пришёл новый.

«Отправить» / «Редактировать» — как раньше: уйти гостю / подставить в поле.

### D7. Support не шлёт `POST /chat`; гость поллит детали

Support-отправка → messages API. Resolve → resolve API. Generate → suggest API.

Гость с `conversation_id` поллит детали раз в 5 с, дописывает `operator` (и `assistant` в auto). `suggested_response` не рендерит.

`/operator`: тот же список эскалаций, панель, `refetchInterval: 5_000`. Без `/api/operator/tickets`.

### D8. `resolved` не принимает ходы гостя

`POST /chat` с `resolved` `conversation_id` → 409.

## Risks / Trade-offs

- [Черновик пустой, пока оператор не нажал кнопку] → это цена экономии токенов; для демо жюри жмёт одну кнопку.
- [Гость знает UUID диалога] → для хакатона достаточно.
- [`auto` снова тратит токены на ход] → не дефолт; в `draft` LLM на гостевом ходе нет.
- [Support случайно вызовет `/chat`] → UI только на messages/suggest/resolve.

## Migration Plan

1. Alembic: `suggested_response`.
2. Пропуск LLM на `escalated`+`draft`, API suggest/messages/resolve.
3. Кнопка в панели.
4. Откат: downgrade колонки; гостевой `/chat` как сейчас.

## Open Questions

Нет. Дефолт `draft`.
