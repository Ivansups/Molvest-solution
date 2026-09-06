## Context

Текущий `.github/workflows/ci.yml` содержит только job `notify` (Telegram) на `push: [main]`.
Все команды для качественных проверок уже существуют как таргеты `Makefile` (`lint-server`,
`lint-frontend`, `test-server`, `test-frontend`) и повторяют то, что требует CI. Dockerfile'ы
`server/Dockerfile` и `frontend/Dockerfile` совпадают со сборкой в `docker-compose.yml`.
Интеграционные pytest-tests используют `TEST_DATABASE_URL`
(дефолт `postgresql+asyncpg://postgres:postgres@localhost:5432/molvest`), создают
`CREATE EXTENSION IF NOT EXISTS vector` и делают `pytest.skip` при недоступной БД
(`server/tests/conftest.py`). GigaChat мокируется фикстурой `llm_mock` — внешние секреты не нужны.

## Goals / Non-Goals

**Goals:**
- Прогонять одни и те же команды, что и локально (`make lint*`, `make test*`), в GitHub Actions.
- Полное покрытие интеграционными pytest в CI: Postgres с pgvector как service container (убрать silent-skip).
- Собрать оба Docker-образа (`api`, `web`) на каждый PR/push, без push в registry.

**Non-Goals:**
- Деплой на хостинг, push в registry, прокидывание GigaChat-секретов в CI.

## Decisions

1. **Один переписанный workflow вместо нескольких** — все новые jobs и текущий `notify` живут
   в одном `.github/workflows/ci.yml`. Минимальный диф поверх существующего файла.
   Альтернатива (отдельные CI-файлы) избыточна — jobs и так оркестрируются в одном файле.

2. **Установка uv через `astral-sh/setup-uv`** — чистый способ получить `uv` без хардкода путей,
   согласуется с `uv run` (make-таргеты). `uv sync --all-groups` ставит dev-зависимости
   (ruff, mypy, pytest) — те же, что при локальной установке через `make install-server`.

3. **Postgres как native service container** — образ `pgvector/pgvector:pg16` (тот же, что в
   `docker-compose.yml`), порт 5432, healthcheck `pg_isready`. env
   `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/molvest`
   совпадает с дефолтом в `conftest.py`, поэтому интеграционные тесты не будут скипаться.
   Альтернатива (`docker run` в step) сложнее и не даёт healthcheck из коробки.

4. **Два отдельных job'а для frontend и backend линта/тестов** — возможность параллельного
   выполнения и изолированный failure. Матрица не нужна: языки разные, таргеты разные.

5. **Telegram остаётся независимым job'ом без `needs`** — по выбору пользователя уведомление
   не привязано к исходу проверок и не подменяет их; падение проверок валит пайплайн само по себе.

6. **`skip_specs: true`** — изменение чисто инфраструктурное (CI), поведение продукта не меняется,
   поэтому спецификации не требуются.

## Risks / Trade-offs

- [Сборка frontend-образа в CI долгая из-за загрузки npm-зависимостей внутри Docker] →
  это штатная стоимость сборки; job сборки отделён от lint/test и не блокирует их быстрое выполнение.
- [Прокси (`if`) в GitHub Actions при pulls from forks убирает секреты] → в workflow нет
  `pull_request_target` и нет доступа к секретам GigaChat, поэтому ограничение не критично;
  Telegram может не слаться для PR из форков — приемлемо, т.к. уведомление второстепенно.
- [Redis не поднимается в CI] → не требуется ни одним target'ом из тасок (`make test*`),
  модельные тесты от БД не зависят.
