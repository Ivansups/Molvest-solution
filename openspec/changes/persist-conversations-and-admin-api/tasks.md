## 1. Persist диалога и сообщений

- [x] 1.1 В `services/agent.py` сделать `run_chat_turn`, принимающий `AsyncSession`; после `ainvoke` создавать/находить `Conversation` и писать user- и assistant-сообщения в одной транзакции; прокинуть сессию из роутера `api/chat.py`. Проверить: новый тест `test_chat_persist` на создание диалога и аппенд в существующий.
- [x] 1.2 Добавить константу гостевой фразы эскалации и записывать `system`-сообщение при `escalated` с непустым текстом. Проверить: тест, что при эскалации answer непустой и сообщение имеет роль `system`.

## 2. Эскалация через transition_status + Escalation

- [x] 2.1 Реализовать сервис эскалации: при `escalated=true` и статусе `open` — `transition_status(open→escalated)` и создание `Escalation`; при уже `escalated` — не создавать вторую строку и не менять статус; вызвать его из persist-потока. Проверить: юнит-тест на идемпотентность (два хода → один `Escalation`, статус остаётся `escalated`) — открыть PR-тест в `test_agent_graph`/`test_documents`-стиле.
- [x] 2.2 Связать запись `Escalation` с ассистентским сообщением (`message_id`, `reason`, `escalated_to`). Проверить: тест, что `Escalation` ссылается на сохранённое сообщение.

## 3. Read-only API диалогов и метрик

- [x] 3.1 В `selectors/conversations.py` — список с фильтрами `date`/`user_id`/`status` и пагинацией; детали по id; агрегаты метрик. Проверить: юнит-тесты селекторов.
- [x] 3.2 В `schemas/conversations.py` и `schemas/metrics.py` — Pydantic-схемы ответов. Проверить: сборка схем в `main.py`.
- [x] 3.3 В `api/conversations.py` — `GET /api/conversations` и `GET /api/conversations/{id}`; `api/metrics.py` — `GET /api/metrics`; зарегистрировать в `main.py`. Проверить: тесты списка, фильтров (`status=escalated`, `user_id`), деталей (404 на неизвестный id) и метрик.
- [x] 3.4 Снять запрет `/api/conversations` в `tests/test_openapi_documents.py` и добавить проверку присутствия новых ручек в OpenAPI. Проверить: `pytest` зелёный.

## 4. Качество

- [x] 4.1 Прогнать `ruff check`, `ruff format --check`, `mypy` по `server/`; исправить замечания.
- [x] 4.2 Прогнать `alembic check`; если нет diff — отметить, что миграции не требуются.
- [x] 4.3 Прогнать полный `pytest`; убедиться, что все тесты (включая новые и старые) зелёные.
