## Why

Сейчас `.github/workflows/ci.yml` на push в main только уведомляет в Telegram —
код вообще не проверяется. Линтеры и тесты есть локально (`make lint`, `make test`),
но в GitHub Actions не запускаются, поэтому регрессии попадают в main незамеченными.

## What Changes

- Добавить запуск GitHub Actions на `pull_request` и `push` в main.
- Job линтеров: `ruff check` / `ruff format --check` / `mypy` (backend) + `eslint` / `tsc` (frontend).
- Job тестов: `pytest` с Postgres (pgvector) как service container + `vitest`; GigaChat не дергается (моки как сейчас).
- Job сборки образов `api` и `web` (`docker build`, без push в registry).
- Падение любого job'а валит пайплайн; Telegram-уведомление остаётся независимым job'ом и не подменяет проверки.
- В README — одна строка, что проверки идут в Actions.

## Capabilities

### New Capabilities
Изменение — CI/инфраструктура, поведение продукта не меняется. Спецификации не требуются (`skip_specs: true`).

### Modified Capabilities
_Пусто — нет изменений требований на уровне спецификаций._

## Impact

- `.github/workflows/ci.yml` — переписывается: добавляются jobs lint/test/build, `on.pull_request`.
- `README.md` — добавляется строка про проверки в Actions.
- Никаких изменений в application-коде, Dockerfile'ах или зависимостях — используются существующие таргеты `Makefile` и Dockerfile'ы.
