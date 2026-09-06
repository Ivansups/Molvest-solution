## 1. Workflow-триггеры и структура

- [x] 1.1 Добавить `pull_request` в `on:` workflow и оставить `push: [main]`; проверить, что в YAML оба триггера присутствуют
- [x] 1.2 Разбить пайплайн на отдельные jobs (lint, test, build, notify) так, чтобы падение любого job'а валило весь run; verify: ревью YAML на отсутствие `continue-on-error`

## 2. Job линтеров

- [x] 2.1 Job `lint-server`: `astral-sh/setup-uv` + `uv sync --all-groups`, затем `make lint-server` (ruff check + format-check + mypy); verify: job зелёный при чистом коде
- [x] 2.2 Job `lint-frontend`: pnpm setup + install, затем `make lint-frontend` (eslint + tsc); verify: job зелёный при чистом коде

## 3. Job тестов

- [x] 3.1 Job `test-server`: PostgreSQL service container (pgvector/pgvector:pg16, порт 5432, healthcheck pg_isready) и env `TEST_DATABASE_URL`; verify: `uv run pytest` проходит без скипов БД
- [x] 3.2 Убедиться, что GigaChat не дёргается в CI (моки как сейчас); verify: тесты проходят без GIGACHAT_API_KEY

## 4. Job тестов frontend

- [x] 4.1 Job `test-frontend`: pnpm install + `pnpm test` (vitest); verify: job зелёный, все тесты проходят

## 5. Job сборки образов

- [x] 5.1 Job `build`: собрать `api` (`docker build server`, контекст ./server) и `web` (`docker build frontend`, контекст ./frontend) без push в registry; verify: оба build успешны

## 6. Дока и фиксация

- [x] 6.1 Добавить в README одну строку, что проверки качества запускаются в GitHub Actions; verify: строка присутствует в README
- [x] 6.2 Прогнать `openspec validate ci-quality-gates` и убедиться, что change валиден; отметить задачи `[x]`
- [x] 6.3 Закоммитить изменения в текущей ветке (Conventional Commit, scope `ci`)
