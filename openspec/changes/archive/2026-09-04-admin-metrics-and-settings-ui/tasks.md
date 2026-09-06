## 1. Backend runtime settings

- [x] 1.1 Добавить in-memory store эффективных значений (`confidence_threshold`, `operator_assist_mode`) с инициализацией из env `Settings`
- [x] 1.2 Реализовать getters `get_effective_confidence_threshold` / `get_effective_operator_assist_mode` и `update_effective_settings`
- [x] 1.3 Добавить `GET` / `PUT /api/settings` на схемах `AgentSettingsOut` / `AgentSettingsUpdate`, защита `require_internal_token`, регистрация в `main.py`
- [x] 1.4 Заменить прямое чтение `settings.confidence_threshold` / `operator_assist_mode` в графе и operator-assist на effective getters
- [x] 1.5 Тесты: GET дефолты; PUT валидный; PUT 422 на плохой порог; после PUT порог влияет на эскалацию; mode readback

## 2. Frontend metrics on screen

- [x] 2.1 Расширить `loadDashboard`: параллельно грузить `GET /api/metrics` с `installation_id`
- [x] 2.2 Обновить `DashboardPage`: три карточки (% автоответов, среднее время, эскалации) + честный error state
- [x] 2.3 Переписать `analytics-service` и `AnalyticsPage` на `GET /api/metrics` (опционально date range); убрать вызов `/api/analytics` и мок-графики/логи (без Grafana/iframe — перспектива отдельно)
- [x] 2.4 Типы ответа метрик во frontend; при необходимости тонкий admin/backend proxy path уже покрыт catch-all; не дублировать формулы метрик на клиенте

## 3. Frontend settings panel

- [x] 3.1 Переписать `settings-service` на `GET` / `PUT /api/settings` с полями threshold + assist mode
- [x] 3.2 Упростить `SettingsPage`: одна форма (порог + `draft`/`auto`); убрать Bitrix/Redmine/models/general, требующие мёртвого API
- [x] 3.3 Unavailable state при ошибке GET; toast при успешном PUT; типы домена под узкий контракт

## 4. Quality and docs

- [x] 4.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .` и релевантные pytest
- [x] 4.2 `pnpm --dir frontend lint && pnpm --dir frontend typecheck` (+ точечные тесты сервисов при наличии)
- [x] 4.3 Обновить `docs/ROADMAP.md` §12: метрики на экране и настройки в панели — закрыты; одной строкой отметить Grafana как возможное продолжение (не сделано)
