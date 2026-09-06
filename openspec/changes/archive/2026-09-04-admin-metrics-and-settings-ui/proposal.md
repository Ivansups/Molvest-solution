## Why

Жюри и админ не видят эффективность агента: `GET /api/metrics` уже считает % автоответов, среднее время и число эскалаций, но дашборд `/` показывает только health и документы, а `/analytics` бьётся в несуществующий `/api/analytics`. Порог уверенности и режим эскалации живут только в env — страница `/settings` зовёт мёртвый `/api/settings`, хотя в ТЗ это настройки панели.

## What Changes

- Показать три метрики из `GET /api/metrics` на дашборде `/` (рядом с health/документами).
- Перевести `/analytics` на те же реальные метрики (без `/api/analytics` и без моков/фейковых графиков).
- Добавить узкий runtime API настроек: `GET` / `PUT /api/settings` для `confidence_threshold` и `operator_assist_mode` (схемы Pydantic уже есть).
- Переписать UI `/settings`: только эти два поля, живой API через существующий прокси; убрать вкладки Bitrix/Redmine/модели и вызовы несуществующих ручек.
- Агент и эскалация читают **эффективные** значения (runtime override поверх env), без хардкода в узлах графа.

## Capabilities

### New Capabilities
- `agent-runtime-settings`: чтение и изменение порога уверенности и режима `draft`/`auto` через REST; эффективные значения применяются к графу без рестарта процесса.

### Modified Capabilities
- `support-console-ui`: дашборд и analytics показывают live-метрики; settings — live API, без unavailable-заглушки для этих двух значений.
- `operator-assist`: снимается запрет «нет публичного settings API»; режим берётся из эффективного runtime-значения.

## Impact

- Backend: новый роутер `/api/settings`, сервис эффективных настроек, чтение порога/режима в графе и operator-assist; тесты API и поведения графа после смены порога.
- Frontend: `DashboardPage`, `loadDashboard`, `AnalyticsPage`/`analytics-service`, `SettingsPage`/`settings-service`, типы; без нового `/api/dashboard` и без `/api/analytics`.
- Документы: закрыть пункты §12 ROADMAP про метрики на экране и настройки в панели (после реализации).
- Вне scope: Bitrix/Redmine, PATCH документов, SSE, обучение на кейсах, персистентность настроек в Postgres, смена моделей GigaChat из UI.
- **Перспектива (не в этом change):** Grafana (или аналог) поверх тех же агрегатов / будущего `/metrics` Prometheus. Консольный UI сейчас — демо для жюри; не дублировать тяжёлую аналитику в Next.js так, чтобы потом мешало подключить внешний дашборд.
