# Redmine HelpDesk

Почтовый/тикетный канал сценария 1. Ядро то же, что у виджета и Bitrix:
`run_chat_turn`. Как агент ветвит ответ и эскалацию — в [README](../README.md).

Живой ящик заказчика на защите не обязателен. Демо без почты — вебхук ниже.

## Вход

Контракт для тестов и демо без почтового ящика: `POST /webhook/redmine`
(тот же служебный заголовок `X-Internal-Token`, что у
`POST /webhook/bitrix`).

Тело: `ticket_id`, `message_id`, `sender` (`user` / `operator`), `text`.
Маппинг тикета на диалог — `ChannelThread(channel="redmine")`.

`workspace_id` лучше задать UUID установки консоли
(`7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11`). Тогда эскалация видна в
`/operator`, а поиск идёт по той же базе знаний, что у виджета. Строка
`redmine` (дефолт схемы) даёт **другой** installation — диалог в консоли
не появится.

Ответ агента — заметка в тикет (`REDMINE_URL` + `REDMINE_API_KEY`) **после**
записи в БД. Без этих переменных вебхук всё равно отвечает: `reply` в JSON,
`delivered=false`. Ниже порога уверенности или при явном «позовите оператора»
в тикет гостю ничего не пишем, черновик — в консоли `/operator`.

IMAP (`REDMINE_IMAP_*`) опционален: пустой хост — поллера нет, вебхук жив.

## Локально без Redmine

```bash
make up
curl -sf http://localhost:8000/health
# {"status":"ok"}

cd server && uv run pytest tests/test_redmine.py
```

Демо «письмо → тикет» — тот же контракт, что тесты. Пустая база почти всегда
даёт эскалацию: `200`, `escalated=true`, `reply=null`, `delivered=false`.
Так задумано (порог), не поломка канала.

`workspace_id` — UUID установки консоли. `ticket_id` только цифры.
`message_id` на каждый запрос новый, кроме проверки дубля.

```bash
# 1. Вопрос гостя (как письмо в тикет)
curl -sS -X POST http://localhost:8000/webhook/redmine \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "42",
    "message_id": "mail-1",
    "sender": "user",
    "text": "как провести документ?",
    "workspace_id": "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11"
  }'

# 2. Тот же message_id → status=duplicate, граф не гоняется
curl -sS -X POST http://localhost:8000/webhook/redmine \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "42",
    "message_id": "mail-1",
    "sender": "user",
    "text": "как провести документ?",
    "workspace_id": "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11"
  }'

# 3. Реплика оператора в том же тикете (граф не запускается)
curl -sS -X POST http://localhost:8000/webhook/redmine \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "42",
    "message_id": "mail-op-1",
    "sender": "operator",
    "text": "сейчас посмотрю",
    "workspace_id": "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11"
  }'

# 4. Нет обязательных полей → 422
curl -sS -X POST http://localhost:8000/webhook/redmine \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"1"}'
```

Если `INTERNAL_SERVICE_TOKEN` в `.env` **задан**, все запросы выше должны
нести заголовок `X-Internal-Token`. Чужой или пустой заголовок → **403**,
запись в БД не идёт. Пустой токен в `.env` — проверка выключена (локальная
разработка), чужой заголовок **не** даст 403.

Чтобы увидеть `reply` в JSON (а не только эскалацию): ключ GigaChat,
хотя бы один проиндексированный документ в админке, режим `auto` или
`draft` на ещё `open` диалоге. Без `REDMINE_URL` / `REDMINE_API_KEY`
ответ всё равно вернётся в теле вебхука, в живой тикет не уйдёт
(`delivered=false`).

Эскалация: http://localhost:3000/operator — тот же `conversation_id`,
что в ответе вебхука.

## Переменные

Канон — [`.env.example`](../.env.example).

| Переменная | Назначение |
| --- | --- |
| `REDMINE_URL` | базовый URL Redmine без хвоста |
| `REDMINE_API_KEY` | ключ REST для заметки в тикет |
| `REDMINE_IMAP_HOST` | хост ящика; пусто — не опрашиваем почту |
| `REDMINE_IMAP_PORT` / `USER` / `PASSWORD` | IMAP |
| `REDMINE_SMTP_*` | запасной исходящий путь, если REST не задан |
| `INTERNAL_SERVICE_TOKEN` | `X-Internal-Token`; пусто — проверка выключена |
