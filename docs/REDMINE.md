# Redmine HelpDesk

Почтовый/тикетный канал сценария 1. Ядро то же, что у виджета и Bitrix:
`run_chat_turn`. Как агент ветвит ответ и эскалацию — в [README](../README.md).

## Вход

Контракт для тестов и демо без почтового ящика: `POST /webhook/redmine`
(тот же служебный заголовок `X-Internal-Token`, что у
`POST /webhook/bitrix`).

Тело: `ticket_id`, `message_id`, `sender` (`user` / `operator`), `text`.
Маппинг тикета на диалог — `ChannelThread(channel="redmine")`.

Ответ агента — заметка в тикет (`REDMINE_URL` + `REDMINE_API_KEY`) **после**
записи в БД. Ниже порога уверенности или при явном «позовите оператора» в
тикет гостю ничего не пишем, черновик — в консоли `/operator`.

IMAP (`REDMINE_IMAP_*`) опционален: пустой хост — поллера нет, вебхук жив.

## Переменные

Канон — [`.env.example`](../.env.example).

| Переменная | Назначение |
| --- | --- |
| `REDMINE_URL` | базовый URL Redmine без хвоста |
| `REDMINE_API_KEY` | ключ REST для заметки в тикет |
| `REDMINE_IMAP_HOST` | хост ящика; пусто — не опрашиваем почту |
| `REDMINE_IMAP_PORT` / `USER` / `PASSWORD` | IMAP |
| `REDMINE_SMTP_*` | запасной исходящий путь, если REST не задан |
