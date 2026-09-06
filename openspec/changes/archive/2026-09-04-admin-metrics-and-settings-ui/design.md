## Context

Этап 6 уже отдаёт `GET /api/metrics` (% автоответов, среднее время ответа, число эскалаций). Дашборд Next.js грузит только `/health` и документы. Страница `/analytics` и `/settings` ходят в несуществующие `/api/analytics` и `/api/settings` и показывают «unavailable». В `server/app/schemas/settings.py` уже лежат `AgentSettingsOut` / `AgentSettingsUpdate`. Порог и `OPERATOR_ASSIST_MODE` читаются из pydantic `Settings` (env). ROADMAP §12 фиксирует обе дыры как открытые.

## Goals / Non-Goals

**Goals:**

- Админ на `/` видит три метрики из живого `GET /api/metrics`.
- `/analytics` показывает те же (или расширенные фильтром дат) метрики без мёртвого API.
- `/settings` читает и сохраняет `confidence_threshold` и `operator_assist_mode` через REST; граф сразу использует новые значения.
- Внутренний токен (`X-Internal-Token`) как у остальных admin-ручек.

**Non-Goals:**

- Новый `/api/dashboard` или `/api/analytics`.
- Bitrix/Redmine, модели GigaChat, SLA, email из текущего макета settings.
- Персистентность настроек в Postgres / Alembic.
- Изменение формул метрик.
- PATCH документов, SSE, каналы.
- **Grafana / Prometheus / OpenTelemetry** — осознанная перспектива после хакатона; в этом change не ставим агент, не пишем exporters, не встраиваем iframe Grafana в консоль.

## Decisions

### D1. Метрики только через существующий `GET /api/metrics`

Дашборд и analytics вызывают одну ручку. Не плодим `/api/analytics` с мок-графиками. На `/` — три карточки; на `/analytics` — те же цифры + опционально `date_from` / `date_to` (параметры API уже есть). Старый `analyticsService.getAnalytics()` и фейковые pie/bar убираем или заменяем.

Консоль остаётся **тонким потребителем** JSON-агрегатов. Источник истины по цифрам — backend (селектор/API), не React-состояние и не захардкоженные серии для Recharts. Так позже проще подставить Grafana: либо scrape/exporter того же домена метрик, либо отдельный Prometheus endpoint рядом с `GET /api/metrics`, без переписывания формул «ради UI».

**Альтернатива:** оставить analytics как «скоро» — отвергнуто: меню ведёт на мёртвую страницу.

**Альтернатива сейчас:** сразу Grafana в Compose — отвергнуто как scope creep; фиксируем только контракт «агрегаты живут на API».

### D2. Узкий `GET` + `PUT /api/settings`

Контракт = уже существующие схемы:

- GET → `{ confidence_threshold, operator_assist_mode }`
- PUT body → то же; валидация `confidence_threshold` ∈ [0.5, 0.99], mode ∈ `draft`|`auto`

Секреты и URL GigaChat / Bitrix в API не входят.

**Альтернатива:** полный `SystemSettings` как на фронте сейчас — отвергнуто (YAGNI, нет бэкенда под поля).

### D3. Runtime override в процессе API, env = дефолт

Эффективные значения хранятся в маленьком in-memory store (модуль `services/runtime_settings.py` или аналог), инициализируются из `settings` при старте. PUT обновляет store. Граф и operator-assist читают **только** через `get_effective_*()`, не `app_settings.confidence_threshold` напрямую в узлах (или тонкая обёртка поверх). Рестарт API сбрасывает к env — для хакатона ок; в README одна строка.

**Альтернатива Redis:** надёжнее при нескольких воркерах, но compose обычно один uvicorn worker; отложено.

**Альтернатива писать в `.env`:** нельзя из контейнера надёжно и небезопасно.

### D4. Frontend settings — упростить форму

Одна карточка: слайдер/инпут порога + select/switch `draft`/`auto`. `settingsService` → `/backend/api/settings` (или admin proxy с токеном), типы под `AgentSettings*`. Вкладки integrations/models/general удалить или не рендерить.

### D5. Дашборд — server-side load метрик

`loadDashboard` параллельно тянет metrics с `installation_id`. `DashboardPage` получает третий `ServerResult`. Ошибка метрик — честный empty/error state, не мок.

## Risks / Trade-offs

- **[Risk] Несколько воркеров uvicorn** → разные in-memory overrides → Mitigation: один worker в compose; при необходимости позже Redis.
- **[Risk] Старый широкий UI settings сломает ожидания** → Mitigation: явный copy «только порог и режим эскалации»; остальное — env.
- **[Risk] Analytics без красивых графиков** → Mitigation: три метрики + период важнее фейковых chart’ов для жюри.
- **[Trade-off] Сброс настроек при рестарте** → приемлемо для демо; дефолты из env всегда валидны.

## Migration Plan

1. Задеплоить API settings + wiring effective values.
2. Обновить фронт дашборда/analytics/settings.
3. Обновить ROADMAP §12 после merge (отдельный docs-коммит или в том же PR).
4. Rollback: убрать роутер/UI; env снова единственный источник (код чтения через getter с fallback на env безопасен).

## Open Questions

- Нет блокирующих для этого change.
- **Позже (вне scope):** Redis persistence для runtime settings; Grafana — scrape Prometheus vs JSON datasource на `GET /api/metrics`; нужны ли time-series (сейчас API отдаёт снимок за период, не ряды точек).
