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
- Параллельно коннектору — контур сценария 1 ТЗ: бот открытой линии + штатный
  онлайн-чат, чтобы клиент печатал в окне Bitrix и получал ответ там же
  (`imbot.message.add`). Кастомный коннектор не удаляем.

**Non-Goals:**

- Импровизированный `/webhook/bitrix` сценария 2 не трогаем.
- Redmine, файловые хранилища, токены в `/settings`, поллинг.
- Гарантированная доставка (retry/queue) исходящих REST-вызовов — только
  попытка после commit + лог ошибки.
- Сценарий 2 на живом портале (черновик оператору в чужом чате) — не этот
  change.
- Удаление или замена кастомного коннектора. Онлайн-чат на портале включается
  вручную в контакт-центре, виджет сайта мы не генерируем.

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
- [Формат `ONIMBOTMESSAGEADD` на живом портале может отличаться от доки] →
  либеральный парсинг; расхождения фиксируем в design после задачи 8.11, как
  с install-payload в D8.
- [Бот не в очереди линии — клиент пишет, ответа нет] → README: посадка в
  очередь контакт-центра вручную; не блокируем код обходным API до проверки.
- [Пустой `BITRIX_HANDLER_BASE_URL`] → install проходит, бот не регистрируется,
  в логе warning без секрета; коннектор не страдает.

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

- ~~Точный JSON-формат события Open Lines REST-коннектора... уточняются на
  тестовом портале~~ — снято, см. D8: обнаружена более серьёзная проблема на
  уровне авторизации, формат события пока не проверен вживую (до него не
  дошли).

## D8. Реальный портал: `imconnector.*`/`imbot.*` требуют OAuth-контекст приложения (пересматривает D2)

**Обнаружено эмпирически** на тестовом портале `b24-adkm07.bitrix24.ru`
21.08.2026 (после подъёма стека и попытки живой регистрации): входящий
вебхук с правами `im`, `imconnector`, `imopenlines`, `disk` **не проходит
авторизацию** ни для `imconnector.register`, ни для `imconnector.send.messages`
(`WRONG_AUTH_TYPE: Application context required`), ни для `imbot.register`
(`insufficient_scope`) — при том что нужный scope выдан. Bitrix24 требует для
этой группы методов контекст установленного OAuth-приложения, а не
статический токен вебхука. Простая проверка `profile.json` тем же вебхуком
проходит нормально — ограничение специфично для методов, создающих
общесистемные сущности (боты, коннекторы), не для чтения/CRM.

Это отменяет решение D2 («валидация токена приложения вместо OAuth») в части
исходящих вызовов: `BITRIX_APP_USER_ID`/`BITRIX_APP_TOKEN` остаются пригодны
для методов, не требующих app-контекста, но `Bitrix24RestClient` для
`imconnector.send.messages` (и любая будущая регистрация бота) должен
использовать OAuth `access_token`, полученный через установку локального
приложения.

**Новый план авторизации:**

1. Локальное серверное приложение в Bitrix24 (уже создаётся вручную на
   портале) даёт `client_id`/`client_secret` — новые `BITRIX_CLIENT_ID`,
   `BITRIX_CLIENT_SECRET` в конфиге.
2. `POST /webhook/bitrix/install` — путь первоначальной установки. Для
   локального серверного приложения (с выключенной галкой «Приложение само
   завершает установку») Bitrix шлёт `event=ONAPPINSTALL`, form-urlencoded, с
   PHP-style вложенными ключами `auth[access_token]`, `auth[refresh_token]`,
   `auth[expires_in]`, `auth[member_id]` — подтверждено живым порталом
   `b24-adkm07.bitrix24.ru`, отличается от более старого плоского формата
   `AUTH_ID`/`REFRESH_ID`, который встречается в части документации/примеров.
   Хендлер сохраняет токен и отвечает HTML, вызывающим `BX24.installFinish()`
   (иначе Bitrix считает установку незавершённой).
3. Новая таблица `bitrix_oauth_tokens` (`member_id`, `access_token`,
   `refresh_token`, `expires_at`) — токены не годятся для статичного env:
   `access_token` живёt ~1 час, `refresh_token` меняется при каждом обновлении.
4. `app/channels/bitrix/oauth.py` — обмен `refresh_token` на новую пару через
   `POST https://oauth.bitrix24.tech/oauth/token/` (`grant_type=refresh_token`,
   `client_id`, `client_secret`) — хост подтверждён полем
   `auth[server_endpoint]` реального установочного payload'а
   (`https://oauth.bitrix24.tech/rest/`), не устаревший `oauth.bitrix.info`;
   вызывается лениво при `expired_token` от REST или проактивно по
   `expires_at`.
5. `Bitrix24RestClient` для `imconnector.*` переключается на
   `https://{domain}/rest/{method}?auth={access_token}`; при `expired_token`
   — один retry после обновления токена.

**Риск**: `refresh_token` инвалидируется, если приложение переустановят или
отключат — тогда `/webhook/bitrix/install` должен снова сработать (Bitrix
всегда шлёт новую установку при переустановке).

**Альтернатива (отклонена)**: остаться на статическом вебхуке и вместо
`imconnector`/`imbot` использовать что-то, не требующее app-контекста —
проверено эмпирически, что и `imbot`, и `imconnector` оба требуют OAuth;
альтернативы внутри тех же REST-групп нет.

## D9. `imconnector.register` требует scope `placement` + явный `PLACEMENT_HANDLER`

Подтверждено на живом портале после D8: даже с OAuth-токеном
`imconnector.register` падает `NO_PLACEMENT_HANDLER`, пока не выполнены оба
условия:

1. Приложению нужен дополнительный scope `placement` («Встраивание
   приложений»), сверх `imconnector`/`imopenlines`/`im`/`disk` — без него
   `placement.bind` падает `insufficient_scope`.
2. `placement.bind` на код `SETTING_CONNECTOR` (не `SALESCENTER_CONNECTOR`,
   как можно предположить по названию раздела «Salescenter» в интерфейсе) с
   `HANDLER` = наш `/webhook/bitrix/openlines`.
3. Даже после успешного `placement.bind`, сам `imconnector.register` всё
   равно требует **тот же URL повторно**, явным параметром
   `PLACEMENT_HANDLER` в теле вызова — привязки плейсмента одной недостаточно.

После выполнения обоих шагов `imconnector.register` и `imconnector.activate`
(с `LINE` = id открытой линии) проходят успешно. Смена scope у уже
установленного приложения требует повторной установки (кнопка
«Переустановить» в карточке приложения) — старый `access_token` не получает
новых прав задним числом.

## D10. Два контура рядом: коннектор остаётся, бот закрывает окно клиента ТЗ

Кастомный коннектор (`bitrix_openlines` / `imconnector.send.messages`)
полезен как труба «внешняя система → оператор», но **не даёт окна, куда
сотрудник пишет как клиент**. Это не баг реализации — так устроен REST-
коннектор. Формулировка сценария 1 ТЗ («пишет вопрос текстом в Bitrix24»)
требует штатную клиентскую поверхность.

Поэтому рядом, без удаления коннектора:

| | Кастомный коннектор (есть) | Бот открытой линии (добавляем) |
| --- | --- | --- |
| Где пишет клиент | Нет UI в Bitrix; только API / внешний канал | Онлайн-чат линии и диалог с ботом в Bitrix |
| Вход | `POST /webhook/bitrix/openlines` | `POST /webhook/bitrix/bot` (`ONIMBOTMESSAGEADD`) |
| `channel` | `bitrix_openlines` | `bitrix_ol_bot` |
| Исходящее | `imconnector.send.messages` | `imbot.message.add` |
| Ядро | `run_chat_turn` | тот же `run_chat_turn` |

Оркестрация бота — новый `services/ol_bot.py` по образцу `openlines.py`, без
рефакторинга рабочего коннектора. Общие инварианты те же: дубль по
`(channel, channel_message_id)`, маппинг через `ChannelThread`, внешний REST
после commit, оператор без графа, эскалация без автоответа.

Альтернатива «переделать коннектор в бота» отклонена: коннектор уже
зарегистрирован на живом портале (D8–D9), для внешних каналов он останется
нужен; ТЗ просит второй вход, не замену.

## D11. Клиентская поверхность — штатный онлайн-чат, не наш HTML

Код не рисует чат Bitrix. На тестовом портале в контакт-центре на **ту же**
`BITRIX_LINE_ID` включается канал «Онлайн-чат» (`livechat`). Сотрудник /
жюри открывают виджет или тестовое окно линии и пишут как клиент. Bitrix
сам кладёт это в открытую линию и зовёт нашего бота.

Регистрация бота (`imbot.register`, тип open line, `OPENLINE=Y`) делает
агента участником линии. Посадку бота в очередь линии при необходимости
дожимаем вручную в UI портала (как `placement` для коннектора) — если REST
привязки не хватит, фиксируем шаги в README, не плодим обходные API.

Альтернатива «наш виджет = клиент ТЗ» отклонена для этого change: виджет
уже закрывает демо, жюри по ТЗ должно увидеть ответ **в Bitrix**.

## D12. Контракт бота — ONIMBOTMESSAGEADD, исходящее imbot.message.add

Вход (либеральный парсинг, как у коннектора): `event=ONIMBOTMESSAGEADD`,
`data[PARAMS][DIALOG_ID]`, `MESSAGE` / `MESSAGE_ID` / `FROM_USER_ID`,
`auth[application_token]` / `domain` / `member_id`. PHP-style form и JSON —
оба. Join/welcome без текста вопроса — не `run_chat_turn`.

Авторство:

- id зарегистрированного бота → игнор (иначе эхо своего `imbot.message.add`);
- оператор открытой линии → `Message(role=operator)`, без графа и без исходящего;
- иначе гость → `run_chat_turn(..., channel="bitrix_ol_bot", ...)`.

Исходящее после commit: `imbot.message.add` с `BOT_ID`, `DIALOG_ID`,
`MESSAGE`. Не `imconnector.send.messages` — тот метод рисует сообщение
*клиента* оператору, а не ответ бота клиенту. OAuth как в D8. Ошибка REST
→ `processed` + `delivered=false` + лог без токена.

Картинка — тот же best-effort, что D6.

## D13. Регистрация бота при install, bot id хранится у OAuth-записи

После успешного `store_installation` (и при переустановке) вызываем
`imbot.register`:

- `CODE` = `BITRIX_BOT_CODE` (env, по умолчанию осмысленный код вроде
  `molvest_support`);
- `EVENT_MESSAGE_ADD` = `{BITRIX_HANDLER_BASE_URL}/webhook/bitrix/bot`;
- тип open line / `OPENLINE=Y`.

`BITRIX_HANDLER_BASE_URL` — публичный URL нашего API (ngrok на демо). Без
него регистрировать нечего: Bitrix должен достучаться до хендлера снаружи.

`imbot.register` не идемпотентен — повтор создаёт второго бота. Поэтому
`bot_id` пишем в `bitrix_oauth_tokens.openlines_bot_id`. Если бот с тем же
`CODE` уже есть (`imbot.bot.list`) — берём его id, не регистрируем снова.

Scope: к списку D9 добавить `imbot`. Смена scope = переустановка приложения
(уже зафиксировано в D9).

Альтернатива «хранить BOT_ID только в env» отклонена: id выдаёт портал после
register, в git его нет, при переустановке он может смениться.

## D14. Конфиг бота

Новые env (образцы без секретов в `.env.example`):

- `BITRIX_BOT_CODE` — код бота на портале;
- `BITRIX_HANDLER_BASE_URL` — публичная база URL хендлеров.

Существующие `BITRIX_LINE_ID` / OAuth / `BITRIX_APPLICATION_TOKEN`
переиспользуются. README: два контура (коннектор vs бот+онлайн-чат), scope
`imbot`, как открыть тестовый онлайн-чат и проверить «написал → бот ответил
в том же окне».