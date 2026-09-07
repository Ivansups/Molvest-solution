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