# Карта тестов

Как гонять и что какой файл закрывает. Живого GigaChat в тестах нет.

## Как запускать

| Команда | Что делает |
| --- | --- |
| `make test` | backend pytest + frontend vitest |
| `cd server && uv run pytest` | только API |
| `cd server && uv run pytest -k documents` | один файл / фильтр |
| `pnpm --dir frontend test` | только UI |

Интеграционные тесты backend ждут Postgres на `localhost:5432` (`TEST_DATABASE_URL` или дефолт `postgres/postgres/molvest`). Нет БД — эти тесты **скипаются** (`Postgres недоступен`), юниты всё равно идут.

```bash
make db
cd server && uv run pytest
```

Расширение `vector` фикстура создаёт сама.

## Что не дергается

- GigaChat API — везде мок SDK, `llm_mock` или `FakeEmbedder`.
- Redis — кэш либо мокается, либо best-effort (падение Redis не валит тест).
- Браузер / Playwright — UI-сценарии чата и админки автотестами не закрыты.

## Backend (`server/tests/`)

Нужна БД = фикстуры `db_session` / `api_client`.

| Файл | БД | Что проверяет |
| --- | --- | --- |
| `test_health.py` | нет | `GET /health` → 200, есть `x-request-id` |
| `test_logging.py` | нет | обрезка текста в логах |
| `test_openapi_documents.py` | нет | в OpenAPI есть `/chat`, `/api/documents`, conversations, metrics |
| `test_chat.py` | нет | `POST /chat` отдаёт результат графа (граф подменён) |
| `test_security.py` | частично | `X-Internal-Token`: 401 / пропуск / health открыт; JSON `{error, detail, request_id}` на 404 и 500 |
| `test_workspace.py` | нет | UUID workspace без hash; обычная строка → стабильный uuid5 |
| `test_gigachat_client.py` | нет | обёртка SDK: текст ответа, data-URL для Vision, модель эмбеддингов |
| `test_conversation_status.py` | нет | `open→escalated→resolved`; запретные переходы |
| `test_agent_graph.py` | частично | граф: empty/greeting/off-topic без LLM; support → retrieve/generate; эскалация без generate; Vision; кэш ответа; история в промпте; persist + идемпотентная эскалация |
| `test_documents.py` | да | upload PDF/DOCX, 422/409, список, карточка, удаление чанков, фон index после upload и reindex |
| `test_rag.py` | частично | чанкинг/HTML/MD без БД; индекс, атомарный reindex, размер вектора, retrieve, FAILED — с БД |
| `test_conversations_api.py` | да | список/фильтры/изоляция installation; детали; 404; метрики (% автоответов, эскалации) |

`conftest.py`: движок Postgres, skip без БД, `api_client` с подменой сессии, общий `llm_mock`.

## Frontend (`frontend/tests/`)

Vitest, без браузера и без FastAPI.

| Файл | Что проверяет |
| --- | --- |
| `user-session.test.ts` | разбор JSON сессии: битые поля → null |
| `session-token.test.ts` | HMAC cookie: round-trip, чужой секрет, порча payload |
| `client-session.test.ts` | `installationId` из клиентского снимка сессии |
| `image.test.ts` | `fitWithin`: мелкое не трогать, длинная сторона ≤ 1024 |

## По сценариям продукта

| Сценарий | Есть автотест | Дыра |
| --- | --- | --- |
| 1. Текстовый Q&A | граф + persist + `/chat` (мок LLM) | нет e2e с живым GigaChat |
| 2. Чат оператора | нет | UI и API тикетов не покрыты |
| 3. Скриншот | Vision-узел графа (мок); ресайз на фронте | нет e2e с картинкой в API |
| 4. База знаний | upload / delete / reindex / RAG | нет UI-теста админки |

## Как читать падения

- Пачка skip с `Postgres недоступен` — не баг, поднимите `make db`.
- Падение `test_gigachat_*` / `test_agent_graph` — сломали контракт клиента или ветки графа, сеть GigaChat ни при чём.
- Падение `test_documents` / `test_rag` / `test_conversations_api` — схема, сессия или сам API.
