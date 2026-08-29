# Molvest AI-Agent

AI-агент техподдержки 1С для АО «Молвест»: ответы по базе знаний (RAG),
анализ скриншотов ошибок 1С, эскалация оператору при низкой уверенности.
Ядро — **GigaChat**.

[Что внутри](#что-внутри) · [Быстрый старт](#быстрый-старт) · [Команды Make](#команды-make) · [Проблемы при запуске](#проблемы-при-запуске)

## Что внутри

| Часть | Стек | Как запускается |
| --- | --- | --- |
| API | FastAPI, Python 3.12, uv | Docker (`make up`) или локально (`make api`) |
| БД | PostgreSQL 16 + pgvector | Docker (`make up` или `make db`) |
| UI | Next.js 16, pnpm | Только локально (`make frontend`) — в Compose нет |

`make up` поднимает Postgres и API и **обязательно** применяет миграции Alembic до того, как API начнёт отвечать. Фронтенд в Compose нет — после `make up` отдельно `make frontend`.

## Быстрый старт

Нужны: [Docker Desktop](https://docs.docker.com/get-started/get-docker/),
[Git](https://git-scm.com/), [Make](https://www.gnu.org/software/make/)
(на macOS уже есть; на Windows — Git Bash или WSL).

```bash
git clone <repo-url>
cd Molvest-solution
make setup          # создаёт .env, поднимает API + Postgres, ждёт /health
make frontend       # http://localhost:3000
```

Проверка API:

| URL | Назначение |
| --- | --- |
| http://localhost:8000/health | живость сервиса (`{"status":"ok"}`) |
| http://localhost:8000/docs | Swagger |
| http://localhost:8000/chat | `POST`, контракт чата |
| http://localhost:5432 | Postgres (`postgres` / `postgres`, БД `molvest`) |
| http://localhost:3000 | Next.js |

> [!IMPORTANT]
> `docker compose` **упадёт без файла `.env`**: в `docker-compose.yml` указан
> `env_file: .env`. `make setup` / `make env` копируют его из `.env.example`.
> Не коммитьте `.env`.

`GIGACHAT_API_KEY` нужен только для реальных ответов модели. `/health`
работает с пустым ключом.

Ключ: [developers.sber.ru/gigachat](https://developers.sber.ru/gigachat).

## Требования для локальной разработки

Если API крутите в Docker, Python и Node на машине не обязательны.
Они нужны для `make api`, `make frontend`, тестов и линтеров.

| Инструмент | Версия | Зачем | Установка |
| --- | --- | --- | --- |
| Docker Desktop | с плагином Compose v2 (`docker compose`) | API + Postgres | [документация Docker](https://docs.docker.com/get-started/get-docker/) |
| uv | любой свежий | Python-зависимости, **не** pip/poetry | [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Python | ≥ 3.12 | ставит сам uv (`server/.python-version`) | через uv |
| pnpm | 11.x (см. `packageManager` в `frontend/package.json`) | фронтенд, **не** npm/yarn | `corepack enable && corepack prepare pnpm@11.17.0 --activate` |
| Node.js | 20+ | Next.js | [nodejs.org](https://nodejs.org/) |

Порты **3000**, **5432**, **8000** должны быть свободны.

```bash
make install        # uv sync + pnpm install
```

## Переменные окружения

Шаблон — [`.env.example`](.env.example). Живой файл — `.env` в **корне** репозитория
(его читает Compose и, при запуске из `server/`, бэкенд).

| Переменная | Обязательна сейчас | Комментарий |
| --- | --- | --- |
| `GIGACHAT_API_KEY` | нет для `/health` | без ключа агент не ответит по сути |
| `GIGACHAT_API_URL` | нет | значение по умолчанию уже в шаблоне |
| `DATABASE_URL` | да для Docker | хост **`db`** — имя сервиса Compose |
| `POSTGRES_USER` / `PASSWORD` / `DB` | да | должны совпадать с URL |
| `CONFIDENCE_THRESHOLD` | нет | порог эскалации, по умолчанию `0.8` |
| `TOP_K`, `MAX_CHUNK_SIZE` | нет | RAG, пока не задействованы |
| `INTERNAL_SERVICE_TOKEN` | нет | Next.js → FastAPI, позже |
| `NEXTAUTH_SECRET`, `NEXTAUTH_URL` | нет | логин админки, позже |

> [!WARNING]
> В `.env` хост БД — `db`. Так и должно быть для контейнера API.
> `make api` **сам** подставляет `localhost`, не меняйте `.env` ради локального uvicorn.
> Если заменить `db` → `localhost` в `.env`, контейнер API перестанет видеть Postgres.

## Команды Make

`make` без аргументов печатает список.

| Команда | Что делает |
| --- | --- |
| `make setup` | `.env` + сборка/запуск Docker + ожидание `/health` |
| `make env` | копирует `.env.example` → `.env`, если файла нет |
| `make up` | Postgres + API, миграции, ожидание `/health` |
| `make down` | остановить контейнеры (данные БД остаются) |
| `make restart` | перезапуск контейнеров |
| `make logs` | логи API и Postgres |
| `make ps` | статус контейнеров |
| `make health` | ждать `GET /health` до 90 с |
| `make db` | только Postgres (для `make api`) |
| `make migrate` | повторный `alembic upgrade head` в уже запущенном API |
| `make api` | uvicorn на машине, `:8000`, hot-reload |
| `make frontend` | `pnpm install` + Next.js на `:3000` |
| `make install` | зависимости backend и frontend |
| `make test` | pytest |
| `make lint` | ruff + mypy + eslint + tsc |
| `make fmt` | автоформат Python |
| `make clean` | `compose down -v` — **удаляет том Postgres** |

Миграции гоняет entrypoint контейнера API перед uvicorn. `make up` не завершится, пока `/health` не ответит (схема уже на месте). `make migrate` нужен, только если применили новую ревизию без перезапуска контейнера.

## Два способа гонять API

### 1. Docker (обычный путь)

```bash
make setup
# правки в server/ подхватываются (--reload + volume ./server)
make logs          # если что-то не поднялось
```

### 2. Uvicorn на машине, БД в Docker

```bash
make db            # Postgres на localhost:5432
make install-server
make api           # DATABASE_URL с localhost выставляется здесь
```

Не запускайте `make up` и `make api` одновременно: оба занимают порт 8000.

## Проверка руками

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}

curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "message_id": "11111111-1111-1111-1111-111111111111",
    "workspace_id": "demo",
    "conversation_id": null,
    "text": "Как провести документ?",
    "image_base64": null,
    "user_id": "u1"
  }'
```

Контракт `POST /chat` — в `server/app/schemas/chat.py` и в OpenAPI (`/docs`).
Документы базы знаний — `http://localhost:8000/docs` → `/api/documents`.

## Проблемы при запуске

**`env file .env not found` / Compose сразу падает**  
Нет `.env` в корне. `make env` или `cp .env.example .env`.

**`make: command not found` (Windows)**  
Используйте WSL или Git Bash, либо те же шаги вручную (см. ниже).

**`Cannot connect to the Docker daemon` / `docker compose` не находится**  
Запустите Docker Desktop. Нужен Compose v2: `docker compose version`.
Старый бинарь `docker-compose` не используется.

**Порт 5432 / 8000 / 3000 занят**

```bash
lsof -i :5432 -i :8000 -i :3000
```

Остановите чужой Postgres/API или смените проброс портов в `docker-compose.yml`.

**API не отвечает, `make health` истекает**

```bash
make ps
make logs
```

Частая причина после первого клона — долгая сборка образа. Дождитесь
`Started server process` в логах `api`.

**`could not translate host name "db"` при `make api`**  
Uvicorn читает `DATABASE_URL` с хостом `db` из `.env`. Запускайте именно
`make api` (он подменяет URL) или экспортируйте
`DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/molvest`.

**`connection refused` к Postgres с хоста**  
Сначала `make db` или `make up`. Пока `pg_isready` не зелёный, подключаться рано.

**`uv: command not found` / `pnpm: command not found`**  
См. таблицу требований. Не ставьте зависимости через pip/npm.

**Первый `pnpm install` ругается на store / Node**  
Нужен Node 20+. Включите Corepack:  
`corepack enable && corepack prepare pnpm@11.17.0 --activate`.

**GigaChat: SSL / 401 / пустой ответ**  
Проверьте `GIGACHAT_API_KEY` в `.env` (без кавычек и пробелов) и
перезапустите API: `make restart`. На `/health` ключ не влияет.

**Сломали БД и хотите с нуля**  
`make clean && make setup` — том Postgres будет пустой.

## Без Make (те же шаги)

```bash
cp .env.example .env
docker compose up -d --build   # API сам сделает alembic upgrade head
curl -s http://localhost:8000/health

# фронтенд
pnpm --dir frontend install
pnpm --dir frontend dev

# локальный backend
docker compose up -d db
cd server
uv sync --all-groups
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/molvest \
  uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/molvest \
  uv run uvicorn app.main:app --reload
```

## Документация

| Файл | Содержание |
| --- | --- |
| [AGENTS.md](AGENTS.md) | стек, слои, инварианты, линтеры |
| [docs/ROADMAP.md](docs/ROADMAP.md) | этапы и критерии готовности |
| [docs/SCENARIOS.md](docs/SCENARIOS.md) | 4 сценария агента |
| [docs/technical spec/](docs/technical%20spec/) | исходное ТЗ хакатона |
