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
| `OPERATOR_ASSIST_MODE` | `auto` (дефолт), `draft` или `agent` — см. таблицу ниже |
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
| `auto` (дефолт) | сырой ответ ИИ, если скор ≥ порога; иначе эскалация | после эскалации следующие реплики гостя снова могут уйти автоответом |
| `draft` | сырой ответ, пока диалог `open`; после эскалации — нет | черновик после эскалации; в виджете — «Сгенерировать» |
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
Форматы загрузки: PDF, DOCX, HTML, Markdown. После `POST` статус
`PENDING`, индексация в фоне → `INDEXED` или `FAILED`.

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

## Каналы

Ядро одно (`POST /chat`). Специфика протокола — в адаптере.

| Канал | Документ |
| --- | --- |
| Виджет `/chat` | [README](../README.md) |
| Bitrix24 (онлайн-чат и коннектор) | [BITRIX.md](BITRIX.md) |
| Redmine HelpDesk | [REDMINE.md](REDMINE.md) |
