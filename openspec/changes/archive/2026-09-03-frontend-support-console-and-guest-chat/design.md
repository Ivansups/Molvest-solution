## Context

Проект уже имеет рабочий backend для `POST /chat`, `GET /health` и
`/api/documents`, но до этой задачи frontend не давал цельной продуктовой
оболочки под guest/support сценарии. Пользователь попросил сделать только
`frontend/`, сохранить живую интеграцию с backend без фейковых ответов и
оформить UI в закрытоконтурном корпоративном стиле Sber x Molvest.

Текущий технический контекст:

- frontend хостится в Next.js, но основная навигация реализована через
  `react-router-dom` внутри catch-all App Router страницы;
- backend пока не публикует auth API, conversation list/history API,
  dashboard API, settings API, analytics API и operator tickets API;
- UI обязан не придумывать данные там, где backend endpoint ещё отсутствует;
- решение должно собираться и в среде без доступа к внешним Google Fonts.

## Goals / Non-Goals

**Goals:**

- Разделить продукт на публичный guest chat и защищённую support-консоль.
- Построить переиспользуемую компонентную структуру со shared shell, public
  header, service layer и общей темой.
- Подключить live frontend-функции к уже опубликованным backend endpoint'ам
  через единый proxy путь `/backend`.
- Сделать деградацию контролируемой: при отсутствии backend API показывать
  explicit unavailable-state, а не mock content.
- Убрать известные runtime/build проблемы: `document is not defined`,
  предзаполненные поля входа, ломающееся окружение detail chat, внешние fonts.

**Non-Goals:**

- Реализация backend auth API и real session persistence.
- Добавление новых backend endpoint'ов для support chat, analytics, settings
  или operator queue.
- Изменение OpenAPI, моделей БД, миграций и серверной бизнес-логики.
- Реалтайм-сокеты, push-уведомления и collaborative operator flows.

## Decisions

### 1. Host the SPA inside a Next catch-all route

Frontend остаётся в Next.js, но приложение рендерится через `app/[[...slug]]`
и `react-router-dom`. Это позволяет сохранить единый SPA experience,
централизованный AppShell и при этом использовать Next как dev/build host.

Alternative considered:

- Разнести всё на отдельные App Router pages. Отказались, потому что это
  увеличило бы объём дублирования layout/navigation и усложнило бы перенос
  уже собранных page-компонентов.

### 2. Separate public and protected shells

Гостевой сценарий использует `PublicPortalHeader` и отдельную hero-композицию,
а support routes рендерятся внутри `AppShell` с sidebar и top header. Это
фиксирует boundary между внешним пользовательским каналом и закрытым контуром
поддержки.

Alternative considered:

- Единый shell для всех страниц. Отказались, потому что гостевой чат не должен
  визуально и навигационно выглядеть как внутренняя админ-панель.

### 3. Proxy all connected backend traffic through `/backend`

`next.config.ts` rewrites `/backend/:path*` в `NEXT_PUBLIC_API_BASE_URL`, а
axios использует только относительный `baseURL: "/backend"`. Это убирает
жёсткую привязку UI к host/port и упрощает локальный dev, Docker и будущий
deploy за reverse proxy.

Alternative considered:

- Ходить в backend напрямую из браузера на `http://127.0.0.1:8000`. Отказались
  из-за CORS/host coupling и менее предсказуемого поведения в разных средах.

### 4. Use structured service errors for missing endpoints

Для endpoint'ов, которых backend пока не публикует, сервисы бросают
`ApiServiceError`, а страницы показывают `ApiStateCard`. Так UI остаётся
честным: support chat list/history, settings, analytics и operator queue
открываются как разделы, но явно объясняют текущее ограничение backend.

Alternative considered:

- Оставить mock data до появления API. Отказались, потому что это создаёт
  ложное впечатление готовности решения и расходится с реальным backend
  контрактом.

### 5. Keep support login local until backend auth exists

Support login остаётся локальным frontend mock через `authService`, потому что
backend auth API отсутствует. При этом routing уже разделяет роли `admin` и
`operator`, чтобы UI мог показать operator-only navigation и workspace.

Alternative considered:

- Полностью скрыть поддержку до появления auth API. Отказались, потому что
  пользователю нужен был демонстрируемый UI support-контура уже сейчас.

### 6. Make runtime and build closed-contour-safe

Browser-only state читается только в client-safe местах, чтобы не ловить
`document is not defined`. Google Fonts были заменены на локальный font stack,
а build script переключён на `next build --webpack`, потому что на текущей
версии Next.js production build через Turbopack падал внутренней ошибкой.

Alternative considered:

- Оставить `next/font/google` и Turbopack. Отказались, потому что это делает
  сборку нестабильной в offline/locked-down среде и даёт не кодовую, а
  инфраструктурную точку отказа.

## Risks / Trade-offs

- [Local auth diverges from future backend auth] → Изолировать это в
  `authService` и `AppContext`, чтобы заменить точечно при появлении API.
- [Some console sections still have no live data] → Показывать explicit
  unavailable states и не маскировать отсутствие endpoint'ов mock-данными.
- [Client-side search over paginated documents can drift from server totals] →
  Использовать это как временный UX слой до появления server-side search/filter.
- [React Router inside Next adds another routing layer] → Держать одну
  catch-all entrypoint и общий routing map в `src/routes/app-router.tsx`.
- [Current Next.js Turbopack build is unstable for this app] → Зафиксировать
  рабочий build path через webpack, не меняя dev ergonomics.

## Migration Plan

1. Деплойнуть только `frontend` изменения без серверных миграций.
2. Убедиться, что `NEXT_PUBLIC_API_BASE_URL` указывает на существующий FastAPI.
3. Запустить `pnpm --dir frontend build` и `pnpm --dir frontend dev`.
4. Проверить guest chat (`/chat`) и support console (`/login`, `/`) на
   окружении с поднятым backend.
5. Если будущий backend начнёт публиковать auth/settings/analytics/operator
   endpoint'ы, заменить unavailable-state реализации на live queries без смены
   layout и routing boundaries.

Rollback:

- Откат ограничивается только `frontend/`; backend контракт не меняется.

## Open Questions

- Какой auth contract будет опубликован backend для support staff?
- Появится ли отдельный conversation API для support chat list/history или это
  останется производным от `POST /chat` и persistence tables?
- Нужны ли отдельные backend endpoints для dashboard aggregation и operator
  queue, или frontend позже должен агрегировать это из нескольких ресурсов?
