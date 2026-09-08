## 1. Конфигурация и документация

- [x] 1.1 `app/core/config.py`: добавить `bitrix_portal_url`, `bitrix_app_user_id`, `bitrix_app_token`, `bitrix_application_token`, `bitrix_connector_id`, `bitrix_line_id` (опционально); проверять загрузкой из env (пустой `bitrix_application_token` допустим, но fail-closed на приёме)
- [x] 1.2 `.env.example`: добавить блок `BITRIX_*` с комментариями и без реальных значений; проверить, что образец не содержит секретов
- [x] 1.3 `README.md`: раздел «Интеграция Bitrix24» — список env, права приложения (Open Lines, `imconnector`, `imopenlines`, `disk`), регистрация webhook-URL на коннекторе; проверить, что раздел собран и ссылается на `.env.example`

## 2. REST-клиент Bitrix

- [x] 2.1 `app/channels/bitrix/rest.py`: `Bitrix24RestClient` (httpx.AsyncClient) с `send_message(connector_id, chat_id, text)` → `imconnector.send.messages` по URL `{portal_url}/rest/{app_user_id}/{app_token}/`; конструктор URL и составление запроса без попадания токена в строки логирования; проверить юнит-тестом с `httpx.MockTransport` и проверкой, что лог не содержит токена

## 3. Схемы событий Open Lines

- [x] 3.1 `app/channels/bitrix/schemas.py`: добавить модели события Open Lines (либеральный парсинг: `auth` с `application_token`/`domain`, `connector` с `connector_id`/`line_id`/`chat_id`, `message` с `id`/author/text, опциональный `files`) и `BitrixOpenLinesResponse` (`conversation_id`, `status: processed|duplicate`, `reply`, `escalated`, `delivered`); проверить pydantic-юнит-тестом парсинга как полного, так и минимального события

## 4. Webhook-роутер

- [x] 4.1 `app/channels/bitrix/openlines.py`: `POST /webhook/bitrix/openlines` — валидация `secrets.compare_digest(application_token, settings.bitrix_application_token)` и домена портала; некорректный/отсутствующий токен → 403 без изменения состояния; кривой формат → 422; делегирует в `services.openlines.process_openlines_event`; проверить тестами 403/422
- [x] 4.2 Зарегистрировать роутер в `app/main.py`; проверить, что `/webhook/bitrix/openlines` появился в OpenAPI (test_openapi_documents)

## 5. Оркестрация открытой линии

- [x] 5.1 `app/services/openlines.py`: ранняя идемпотентность по `(channel="bitrix_openlines", channel_message_id)` → ответ `duplicate` без персиста, графа и исходящего вызова; проверить тестом повторной доставки того же message id
- [x] 5.2 Маппинг сессии: `ChannelThread(channel="bitrix_openlines", thread_id=chat_id, installation_id=workspace_to_installation_id(domain))`; первый гость создаёт `open`-диалог и маппинг, повторное сообщение сессии продолжает тот же диалог; другой портал с тем же `chat_id` — свой диалог; проверить тестами маппинга
- [x] 5.3 Операторское событие: `Message(role=operator)` в существующий диалог, без запуска графа и без исходящего REST; проверить тестом (в ленте ровно одно сообщение)
- [x] 5.4 Гость: построить `ChatRequest` (детерминированный uuid5 от message id, `workspace_id=domain`, `conversation_id` из маппинга или `None`, `image_base64` из вложения при доступности) и вызвать `run_chat_turn(channel="bitrix_openlines", channel_message_id=...)`; `escalated=False` → после commit отправить `send_message` и вернуть `delivered=true`; `escalated=True` → исходящий вызов не делается (`delivered=false`); недоступное вложение → обработка как текст с warning без падения; проверить тестами с mock-клиентом (порядок commit до send)

## 6. Тесты и quality gate

- [x] 6.1 `server/tests/test_bitrix_channel.py`: позитивные и негативные кейсы по спецификации — первое сообщение создаёт диалог, неверный токен → 403, маппинг «другой портал» на 6.1, дубль вызывается дважды (идемпотентность), автоответ уходит в тот же диалог после commit, эскалация ничего не шлёт, оператор не активирует отправку, секреты не в ответах и не в логах; проверить `uv run pytest server/tests/test_bitrix_channel.py`
- [x] 6.2 Прогнать quality gate после всех правок Python-файлов: `uv run ruff check .` и `uv run ruff format --check .` и `uv run mypy .` и `uv run pytest` и `uv run alembic check` (новых миграций не ожидается — инфраструктура переиспользуется); при ошибках исправить до зелёного прогона

## 7. OAuth для imconnector/imbot (см. design.md D8)

Обнаружено эмпирически на живом портале: `imconnector.*` и `imbot.*`
отклоняют статический вебхук-токен (`Application context required` /
`insufficient_scope`) независимо от выданных scope. Без OAuth реальная
отправка сообщений и регистрация коннектора/бота не проходят авторизацию.

- [x] 7.1 `app/core/config.py`: добавить `bitrix_client_id`, `bitrix_client_secret`; `.env.example` — новые переменные без реальных значений
- [x] 7.2 `app/models/bitrix_oauth.py`: `BitrixOAuthToken` (`member_id` unique, `access_token`, `refresh_token`, `expires_at`, `updated_at`); Alembic-миграция
- [x] 7.3 `app/channels/bitrix/oauth.py`: `exchange_refresh_token(refresh_token) -> TokenPair` через `POST https://oauth.bitrix24.tech/oauth/token/` (`grant_type=refresh_token`, `client_id`, `client_secret`); секреты не логируются
- [x] 7.4 `app/channels/bitrix/install.py`: `POST /webhook/bitrix/install` — читает `auth[access_token]`/`auth[refresh_token]`/`auth[expires_in]`/`auth[member_id]` (`event=ONAPPINSTALL`) из тела, upsert в `BitrixOAuthToken`, отвечает HTML с `BX24.installFinish()`; регистрация роутера в `main.py`
- [x] 7.5 `Bitrix24RestClient`: для `imconnector.*`-вызовов — авторизация через сохранённый `access_token` (`?auth=...`), а не `BITRIX_APP_TOKEN`; заодно закрыт SSRF в `download_image` (хост ссылки должен совпадать с доменом портала, редиректы отключены)
- [x] 7.6 Тесты (`test_bitrix_oauth.py`, 7 шт.): install-хендшейк создаёт запись токена, 422 без обязательных полей, секреты не в ответе, `get_current_access_token` отдаёт валидный и обновляет протухший, `None` без установки, ошибка refresh поднимает `BitrixOAuthError`; `test_bitrix_channel.py` обновлён под новый обязательный `access_token`
- [x] 7.7 Ручная проверка на тестовом портале `b24-adkm07.bitrix24.ru`: установка через `/webhook/bitrix/install` подтверждена (`event=ONAPPINSTALL`, реальный формат полей — обновлено в design.md/proposal.md/specs). `imconnector.register`/`imconnector.activate` с OAuth-токеном прошли успешно (`WRONG_AUTH_TYPE` не возникает). По пути найдено два недокументированных требования реального портала: (1) нужен доп. scope `placement` + `placement.bind` на `SETTING_CONNECTOR` до регистрации коннектора; (2) `imconnector.register` дополнительно требует явный `PLACEMENT_HANDLER` в теле вызова — одного `placement.bind` недостаточно, иначе `NO_PLACEMENT_HANDLER`
- [x] 7.8 Quality gate: `ruff check . && ruff format --check . && mypy . && pytest && alembic check` — 126 тестов зелёных на реальном Postgres, миграция 004 накатилась чисто

## 8. Бот открытой линии рядом с коннектором (сценарий 1 ТЗ, design.md D10–D14)

Кастомный коннектор не трогаем. Рядом — окно клиента: штатный онлайн-чат
линии + `imbot`, чтобы сотрудник писал в Bitrix и получал ответ агента в
том же диалоге.

- [x] 8.1 `app/core/config.py` + `.env.example`: `bitrix_bot_code`,
      `bitrix_handler_base_url`; пустой handler base на регистрации бота —
      явное предупреждение в лог, без падения install. Проверить загрузкой
      из env, в образце нет секретов
- [x] 8.2 Модель: nullable `openlines_bot_id` у `BitrixOAuthToken` + Alembic
      миграция с понятным именем. Проверить `uv run alembic check`
- [x] 8.3 `channels/bitrix/schemas.py`: либеральный парсинг `ONIMBOTMESSAGEADD`
      (DIALOG_ID, MESSAGE, MESSAGE_ID, FROM_USER_ID, auth.application_token /
      domain; form PHP-style и JSON). Юнит-тест полного и минимального события
- [x] 8.4 `Bitrix24RestClient`: `register_openlines_bot`, `list_bots`,
      `send_bot_message` → `imbot.register` / `imbot.bot.list` /
      `imbot.message.add` через OAuth (`?auth=`), токен не в логах. Юнит-тест
      с `httpx.MockTransport`
- [x] 8.5 После `store_installation`: найти бота по `BITRIX_BOT_CODE` или
      зарегистрировать с `EVENT_MESSAGE_ADD={BITRIX_HANDLER_BASE_URL}/webhook/bitrix/bot`,
      сохранить `openlines_bot_id`. Повтор install не создаёт второго бота.
      Тест на первую установку и на reuse
- [x] 8.6 `POST /webhook/bitrix/bot`: та же fail-closed проверка токена, что у
      openlines (403 без записи); 422 на кривой формат; делегирует в сервис.
      Зарегистрировать роутер в `main.py`. Тесты 403/422 + путь в OpenAPI
- [x] 8.7 `app/services/ol_bot.py` по образцу `openlines.py`, без рефакторинга
      коннектора: `channel="bitrix_ol_bot"`; дубль → `duplicate`; автор = bot
      id → игнор без персиста; оператор → `Message(role=operator)` без графа
      и без REST; гость → `run_chat_turn`; `escalated=False` → после commit
      `imbot.message.add` в тот же `DIALOG_ID`; `escalated=True` → исходящего
      нет. Не вызывать `imconnector.send.messages`. Тесты с mock-клиентом
      (порядок commit до send, эхо бота, эскалация, маппинг не пересекается
      с `bitrix_openlines`)
- [x] 8.8 `README.md`: два контура (коннектор vs бот+онлайн-чат); scope `imbot`;
      включить онлайн-чат на `BITRIX_LINE_ID`; проверка «написал в окне Bitrix
      → ответ бота в том же диалоге». Существующий раздел коннектора не
      удалять
- [x] 8.9 `server/tests/test_bitrix_ol_bot.py` + регрессия
      `test_bitrix_channel.py`: коннекторный путь после добавления бота жив.
      Дубль события вызвать дважды. Секреты не в ответах и не в логах
- [x] 8.10 Quality gate после правок Python: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest && uv run alembic check`
- [ ] 8.11 Ручная проверка на `b24-adkm07.bitrix24.ru`: переустановка с scope
      `imbot`, бот появляется, в онлайн-чате линии сообщение клиента получает
      ответ агента в том же окне; коннекторный диалог по-прежнему принимает
      `imconnector.send.messages`. Зафиксировать расхождения формата события
      в design.md, как в 7.7