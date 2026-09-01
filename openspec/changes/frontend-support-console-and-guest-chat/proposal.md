## Why

Текущий проект уже имеет backend-контур для `POST /chat`, `GET /health` и
операций с документами базы знаний, но без цельного frontend-интерфейса
решение нельзя показать как готовый продукт для хакатона и внутреннего
демо. Нужен строгий корпоративный UI, который разделяет публичный гостевой
чат для пользователей 1С и защищённую support-панель для сотрудников.

## What Changes

- Построить компонентный frontend-контур в `frontend/` на React/Next, shadcn/ui
  и Tailwind с единой темой в стилистике Sber x Molvest.
- Разделить маршруты на публичный гостевой чат (`/chat`) и защищённую панель
  поддержки (`/login`, `/`, `/chat/support`, `/knowledge-base`, `/settings`,
  `/analytics`, `/operator`).
- Подключить frontend к уже опубликованным backend endpoint'ам через proxy
  `Next -> /backend -> FastAPI` для `GET /health`, `POST /chat` и
  `/api/documents`.
- Убрать mock-ответы и сделать честные unavailable-state экраны для разделов,
  где backend ещё не публикует нужные endpoint'ы (`/api/conversations`,
  `/api/dashboard`, `/api/settings`, `/api/analytics`, `/api/operator/tickets`).
- Исправить runtime/build шероховатости фронта: SSR-safe инициализацию,
  контрастную тему, корректную навигацию между support-страницами,
  placeholder-поля входа вместо предзаполненных значений и сборку без
  зависимости от внешних Google Fonts.

## Capabilities

### New Capabilities

- `guest-chat-ui`: публичный чат без авторизации для вопросов по 1С с
  отправкой текста и скриншотов в существующий backend `/chat`.
- `support-console-ui`: защищённая support-панель с dashboard, knowledge base,
  support chat, analytics, settings и operator workspace в едином shell.
- `frontend-runtime-integration`: frontend proxy, service layer и runtime
  решения, которые подключают UI к существующим backend endpoint'ам, избегают
  SSR/build проблем и честно обрабатывают недоступные API.

### Modified Capabilities

<!-- None. -->

## Impact

- Affected code: `frontend/app/*`, `frontend/src/routes/*`,
  `frontend/src/components/**/*`, `frontend/src/services/**/*`,
  `frontend/src/store/*`, `frontend/src/api/client.ts`,
  `frontend/next.config.ts`, `frontend/package.json`.
- APIs consumed: `GET /health`, `POST /chat`, `GET/POST/DELETE /api/documents`,
  `POST /api/documents/{id}/reindex`.
- Runtime/build impact: support-only local auth mock remains in frontend until a
  real backend auth API exists; production build uses a stable local font stack
  and `next build --webpack` for the current Next.js version.
- Out of scope: backend auth, new backend support-chat endpoints, analytics API,
  operator ticket API, settings persistence API, database or OpenAPI changes.
