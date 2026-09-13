# Эксплуатация

Как крутить **уже запущенную** систему. Старт и Make — в
[README](../README.md) и [DEV.md](DEV.md). Секреты в этот файл не кладём —
только имена переменных.

## Живость: `GET /health`

```bash
curl -sf http://localhost:8000/health
# {"status":"ok"}
```

`200` и `{"status":"ok"}` значат: процесс API отвечает. Маршрут открытый
(служебный токен не нужен). Ключ GigaChat, Postgres, Redis и база знаний
**не** проверяются: без ключа и без документов `/health` всё равно живой,
а ответа по 1С не будет.

На дашборде консоли (`/`) тот же статус приходит через `/backend/health`.
Swagger: http://localhost:8000/docs.

## Переменные окружения (имена)

Канон — [`.env.example`](../.env.example). Живой файл — `.env` в корне.
Значения секретов сюда не копируем.

Смена переменных у контейнера API: пересоздать сервис
(`docker compose up -d --force-recreate api`), обычный restart `.env` не
перечитывает. Порог и режим после старта можно сменить без рестарта —
см. [настройки](#порог-и-режимы).

### Ядро

| Переменная | Зачем |
| --- | --- |
| `GIGACHAT_API_KEY` | ответы, Vision, эмбеддинги; без ключа `/health` жив |
| `GIGACHAT_SCOPE` / `GIGACHAT_API_URL` / `GIGACHAT_MODEL` | кабинет и модель |
| `GIGACHAT_EMBEDDINGS_MODEL` | модель эмбеддингов (колонка `vector(1024)`) |
| `GIGACHAT_VERIFY_SSL_CERTS` | проверка сертификата НУЦ |
| `GIGACHAT_TIMEOUT` | generate / Vision |
| `GIGACHAT_CLASSIFY_TIMEOUT` / `GIGACHAT_CLASSIFY_MODEL` | YES/NO хэндоффа через GigaChat |
| `OPENROUTER_API_KEY` | детект «позовите оператора»; пусто — тот же детект через GigaChat |
| `OPENROUTER_BASE_URL` / `OPENROUTER_MODEL` / `OPENROUTER_TIMEOUT` | классификатор хэндоффа |
| `DATABASE_URL` | Postgres (хост `db` в Compose) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | должны совпадать с URL |
| `REDIS_URL` | кэш эмбеддингов запроса и готовых ответов |
| `CONFIDENCE_THRESHOLD` | порог эскалации, по умолчанию `0.8` |
| `OPERATOR_ASSIST_MODE` | `draft` (дефолт), `auto` или `agent` — см. таблицу ниже |
| `TOP_K` | сколько чанков в поиск |
| `MAX_CHUNK_SIZE` / `CHUNK_OVERLAP` | чанкинг при индексации |
| `INTERNAL_SERVICE_TOKEN` | Next.js → FastAPI (`X-Internal-Token`); пусто — проверка выключена |
| `API_INTERNAL_URL` | URL FastAPI для контейнера `web` |
| `AUTH_SECRET` | подпись JWT-куки входа в консоль |
| `AUTH_DATABASE_URL` | та же БД, Prisma, схема `auth` |

### Каналы

Имена `BITRIX_*` — в [BITRIX.md](BITRIX.md) (§ 10). Имена `REDMINE_*` —
в [REDMINE.md](REDMINE.md). Access/refresh OAuth Bitrix в `.env` не кладём.

## Порог и режимы

Одна константа порога и одно поле режима. Env задаёт дефолт процесса.
После старта эффективные значения — `GET` / `PUT /api/settings`
(тот же служебный токен, что у админ-API) или страница консоли
`/settings`. Рестарт API не нужен. Порог в `PUT`: `0.5`–`0.99`.
Неизвестное значение режима — `422`, override не меняется.

Секреты каналов и GigaChat через settings **не** принимаются.

| `operator_assist_mode` | Что видит гость | Что делает оператор |
| --- | --- | --- |
| `auto` | сырой ответ ИИ, если скор ≥ порога; иначе эскалация | после эскалации следующие реплики гостя снова могут уйти автоответом |
| `draft` (дефолт) | сырой ответ, пока диалог `open`; после эскалации — нет | черновик после эскалации; в виджете — «Сгенерировать» |
| `agent` | **никогда** сырой ответ ИИ, пока оператор не нажмёт «Отправить» | каждый сгенерированный текст — черновик `suggested_response`; диалог эскалируется |

Значение `agent` — режим настройки, не LangGraph: ИИ не пишет в гостевой
чат (виджет, Bitrix, Redmine), пока оператор не отправит черновик из
`/operator` или `/chat/support`.

На защите Q&A «написал → бот ответил» удобнее `auto` или `draft`.
Режим `agent` — когда заказчик хочет, чтобы человек подтверждал каждый
ответ.

Скор ниже порога → эскалация без generate (во всех трёх режимах).
Порог один, не дублируется по сценариям.

## База знаний

Консоль: `/knowledge-base` (карточка документа — `/knowledge-base/{id}`).
Форматы загрузки: PDF, DOCX, HTML, Markdown; `.doc` (Word 97–2003)
принимается, но извлечение текста лучшее усилие — при неудаче
конвертируйте в DOCX. После `POST` статус `PENDING`, индексация в
фоне → `INDEXED` или `FAILED`.

Все маршруты ниже требуют `installation_id` (query или form). Чужая
установка или нет документа — `404`. При заданном
`INTERNAL_SERVICE_TOKEN` — заголовок `X-Internal-Token`.

| Метод | Путь | Что делает |
| --- | --- | --- |
| `GET` | `/api/documents` | список (фильтры `status`, `file_type`, страница) |
| `POST` | `/api/documents` | загрузка файла (`multipart`: `file`, `title`, `installation_id`, опционально `metadata`) |
| `GET` | `/api/documents/{id}` | карточка + чанки |
| `PATCH` | `/api/documents/{id}` | **только** `title` и/или `metadata`, **без** реиндекса |
| `DELETE` | `/api/documents/{id}` | документ и чанки |
| `POST` | `/api/documents/{id}/reindex` | пересобрать чанки и эмбеддинги |

`PATCH` — JSON `{ "title"?: string, "metadata"?: object }`. Нужно хотя бы
одно поле, иначе `422`. Файл, чанки, `status` и `kb_version` не трогаем:
смена названия или категории не гоняет эмбеддинги. Категория и описание
живут в JSON `metadata` (ключи `category`, `description`). Повторный
PATCH с теми же значениями идемпотентен по смыслу. Чтобы обновить текст
файла — заново загрузить или `reindex`.

Пустая проиндексированная база почти всегда даёт эскалацию: это порог,
не поломка канала.

### Ручная загрузка публичной документации 1С

Скрипт **не** вызывается при `make up`, из Dockerfile или entrypoint.
Только руками, когда стек уже живой и есть ключ GigaChat (эмбеддинги).

```bash
./scripts/ingest_1c_docs.sh
```

Скачивает ~12 открытых файлов в `server/data/1c-docs-cache/` и гоняет
их через тот же upload + атомарный reindex, что и админка. Повторный
запуск: уже скачанные файлы не качает, уже загруженные имена
пропускает (обход 409 на то же имя).

Полный ITS (`its.1c.ru`) за paywall — его не качаем. Источники:

| Файл | Откуда |
| --- | --- |
| PDF руководств пользователя / установки | открытый каталог `v8.1c.ru/upload/static/` |
| PDF «1С:Общепит» | `solutions.1c.ru` (реестр решений) |
| HTML обзор, требования, библиотеки | публичные страницы `v8.1c.ru` |
| статьи «1С:Предприятие», «1С:Бухгалтерия» | Википедия, CC BY-SA |

Переменные: `INSTALLATION_ID` (дефолт тот же, что у консоли —
`7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11`), `CACHE_DIR`,
`FORCE_DOWNLOAD=1`, `INGEST_LOCAL=1` (uv на хосте, без
`docker compose exec`). Для локального uv хост `db` в
`DATABASE_URL` подменяется на `localhost`.

## Каналы

Ядро одно (`POST /chat`). Специфика протокола — в адаптере.

| Канал | Документ |
| --- | --- |
| Виджет `/chat` | [README](../README.md) |
| Bitrix24 (онлайн-чат и коннектор) | [BITRIX.md](BITRIX.md) |
| Redmine HelpDesk | [REDMINE.md](REDMINE.md) |
