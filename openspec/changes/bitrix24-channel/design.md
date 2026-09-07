## Context

Инварианты уже есть в коде: `run_chat_turn` (services/agent.py) переиспользуется
`POST /chat` и `live_thread`; `add_user_message`/`persist_guest_hold`/`persist_turn`
принимают `channel`/`channel_message_id`; `ChannelThread` мапит
`(channel, thread_id, installation_id) → conversation_id` с уникальным ключом;
`messages.channel` + `messages.channel_message_id` дают реестр обработанных
событий с уникальным индексом `uq_messages_channel_message_id`. Сценарий 2
(live-тред) использует `channel="bitrix"` и импровизированный `/webhook/bitrix`
с `require_internal_token`. Мотивация — см. proposal.md (Why).

## Goals / Non-Goals

**Goals:**

- Реальный входящий контур: `POST /webhook/bitrix/openlines` принимает событие
  открытой линии портала (сессия open lines, author id, message id, текст,
  при необходимости файл/картинка) и валидирует токен приложения.
- Маппинг «id сессии открытой линии → `conversation_id`» и идемпотентность
  повторов — через существующие `ChannelThread` и уникальный индекс
  `messages.(channel, channel_message_id)`, без новых таблиц.
- Ответ агента в тот же диалог: после commit состояния — `imconnector.send.messages`
  через единый Bitrix REST-клиент в `channels/bitrix/rest.py`.
- Секреты только env `BITRIX_*`; лог и ответы без токена.

**Non-Goals:**

- Импровизированный `/webhook/bitrix` сценария 2 не трогаем.
- Redmine, файловые хранилища, токены в `/settings`, поллинг.
- Гарантированная доставка (retry/queue) исходящих REST-вызовов — только
  попытка после commit + лог ошибки.

## Decisions

### D1. Новый эндпоинт вместо перегрузки существующего

`POST /webhook/bitrix/openlines` (новый роутер `channels/bitrix/openlines.py`,
регистрация в `main.py`). Существующий `/webhook/bitrix` (`channel="bitrix"`,
внутренний токен) остаётся без изменений. Раздельные пути и раздельные значения
`channel` убирают путаницу форматов событий и маппингов сценариев 1 и 2.

### D2. Валидация события — токен приложения, а не внутренний токен

Событие Open Lines REST-коннектора приносит `auth` с `application_token` и
`domain`. Роутер не требует `X-Internal-Token`: проверяем
`secrets.compare_digest(application_token, settings.bitrix_application_token)` и
домен портала совпадает с хостом `settings.bitrix_portal_url`. Fail-closed: при
пустом `BITRIX_APPLICATION_TOKEN` все события отклоняются (403), секрет не
логируется. Импровизированный вебхук продолжает жить под внутренним токеном.

Альтернатива (внутренний токен) отклонена: Bitrix не знает наш токен и не умеет
его слать; подпись события плюс токен приложения — штатный способ.

### D3. Маппинг и идемпотентность — переиспользование сценария 2

Ключ диалога ОЛ — `chat_id` сессии открытой линии из события (таблица ROADMAP
§14.2: «Bitrix24 | id чата / сессии открытой линии»). Маппим его в
`ChannelThread` с `channel="bitrix_openlines"`, `thread_id=chat_id`,
`installation_id=workspace_to_installation_id(domain портала)` (тот же uuid5,
что в `POST /chat`). Отдельное значение `channel` держит два набора маппингов
непересекающимися.

Идемпотентность — существующий `uq_messages_channel_message_id`:
`Message(channel="bitrix_openlines", channel_message_id=<message id>)`. Ранний
SELECT → `duplicate` без персиста и графа. Повтор `user` в auto и повтор
операторского события покрываются одинаково.

Альтернатива (отдельная таблица `bitrix_dialog_id`) отклонена: `ChannelThread`
уже несёт ровно этот контракт, новая таблица — дублирование структуры.

### D4. Оркестрация — `services/openlines.py` по образцу `live_thread`

`process_openlines_event(session, event)`:

1. Ранний SELECT дубля → `duplicate`.
2. Если `author_id` — оператор портала: пишем `Message(role=operator)`,
   коммит, ответ без графа и без исходящего REST (как в сценарии 2).
3. Иначе гость: по маппингу получаем/отсутствует `conversation_id`, строим
   `ChatRequest` (детерминированный uuid5 `message_id`, `text`, описание
   картинки через vision при вложении, `workspace_id=domain`), вызываем
   `run_chat_turn(request, session, channel="bitrix_openlines",
   channel_message_id=...)`.
4. Маппинг сессии создаётся при его отсутствии (новый диалог).
5. `response.escalated` → ничего не отправляем (оператор подхватывает в
   портале); иначе `reply=response.text` и после commit — исходящий REST в ту
   же линию. Статус ответа с `delivered` флагом.

Draft-режим: `run_chat_turn` сам держит поведение (ветка hold для escalated +
draft); отдельная draft-генерация для оператора в консоли (сценарий 2) в ОЛ-канал
не копируется — Q&A сценария 1 идёт полным графом.

### D5. Исходящий REST — единый клиент в `channels/bitrix/rest.py`

`Bitrix24RestClient` (httpx.AsyncClient): базовый URL
`{bitrix_portal_url}/rest/{bitrix_app_user_id}/{bitrix_app_token}/`, один метод
`send_message(connector_id, chat_id, text)` → `imconnector.send.messages`
(после commit, вне бизнес-транзакции — инвариант AGENTS.md). `connector_id` и
`line_id` — из env (`BITRIX_CONNECTOR_ID`, `BITRIX_LINE_ID`), не захардкожены.
Недоступность/ошибка REST логируется, вебхук всё равно возвращает `processed` с
`delivered=false` (гарантированная доставка — вне scope). Секрет-токен никогда
не логируется, URL компонуется без него в логах.

### D6. Вложение-картинка — best-effort

Если событие несёт файл/картинку, пробуем скачать первый файл через REST
клиент по временному file id события и передать `image_base64` в `ChatRequest`
(граф уже умеет vision). Недоступный файл — обрабатываем как текст, пишем
warning, роутер не падает. Демо сценария 1 — текстовые вопросы, поэтому это
не блокер.

### D7. Конфигурация

В `core/config.py` добавляются `bitrix_portal_url`, `bitrix_app_user_id`,
`bitrix_app_token` (ключ исходящего вебхука), `bitrix_application_token`
(секрет валидации входящего), `bitrix_connector_id`, `bitrix_line_id`
(опционально). В `.env.example` — образцы без реальных значений; в README —
раздел с env и правами приложения (Open Lines, `imconnector`,
`imopenlines`, `disk` для файлов).

## Risks / Trade-offs

- [Документация Bitrix недоступна с наших инструментов: точные поля события и
  сигнатура `imconnector.send.messages` уточняются] → контракт парсится
  либерально (только нужные поля, остальное игнор), исходящий вызов принимает
  гибкие параметры; валидация на тестовом портале до релиза.
- [Ошибка исходящего REST после commit] → `processed` + `delivered=false` + лог;
  очередь/retry вне scope.
- [Секрет попадёт в лог запроса/ответа] → middleware логирует только метод и
  path, не тело; в клиенте body без токена; constant-time сравнение токена.
- [Два параллельных события одной сессии] → уникальный ключ `ChannelThread` +
  `uq_messages_channel_message_id` не дадут дублей; SELECT-first достаточно для
  демо (как в сценарии 2), catch не добавляем.
- [Вложение не скачается в демо] → fallback на текст с warning, сценарий 1 не
  блокируется.

## Migration Plan

1. Новых БД-объектов нет: переиспользуются `channel_threads` и колонки
   `messages.channel`/`channel_message_id` (миграция 003 уже применена).
2. `channels/bitrix/rest.py` (клиент), схемы Open Lines в `schemas.py`,
   `channels/bitrix/openlines.py` (роутер), `services/openlines.py` (логика),
   регистрация в `main.py`, env в `core/config.py` + `.env.example`, README.
3. Тесты `server/tests/test_bitrix_channel.py`: валидация токена, маппинг,
   дубль, операторское событие, исходящий REST после commit, `delivered` флаг,
   отсутствие секретов в ответе/логах.
4. На тестовом портале: зарегистрировать webhook URL на коннектор ОЛ, задать
   env, проверить сообщение → ответ в том же диалоге.
5. Откат: убрать `include_router(openlines_router)`; входящие события портала
   перестанут обрабатываться, живые данные не меняются (все изменения только в
   новых записях под `channel="bitrix_openlines"`).

## Open Questions

- Точный JSON-формат события Open Lines REST-коннектора (имена полей
  `auth`/`params[connector]`/`params[message]`) и точная сигнатура
  `imconnector.send.messages` уточняются на тестовом портале — не влияет на
  подход (либеральный парсинг, гибкая отправка) и на split задач.