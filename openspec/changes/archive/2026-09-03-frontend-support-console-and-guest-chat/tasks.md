## 1. Routing and shared shells

- [x] 1.1 Разделить guest и support маршруты в `frontend/src/routes/app-router.tsx`
- [x] 1.2 Вынести защищённый shell с sidebar/header и сохранить его на detail chat маршруте
- [x] 1.3 Добавить public header и связные переходы между `/chat` и `/login`

## 2. Corporate UI and page composition

- [x] 2.1 Собрать страницы из переиспользуемых shadcn/ui-компонентов и общих блоков
- [x] 2.2 Настроить тему и контраст в стилистике Sber x Molvest без топорного mock-like вида
- [x] 2.3 Убрать предзаполненные credentials и перевести логин на placeholder-based UX

## 3. Live backend integration

- [x] 3.1 Настроить `Next` rewrite proxy `/backend/:path*` на существующий FastAPI
- [x] 3.2 Подключить гостевой чат к live `POST /chat` и убрать fallback-мок ответы
- [x] 3.3 Подключить dashboard и knowledge base к `GET /health` и `/api/documents`
- [x] 3.4 Перевести support-only разделы без backend endpoint'ов на honest unavailable states

## 4. Runtime hardening

- [x] 4.1 Исправить SSR-safe инициализацию frontend state и убрать риск `document is not defined`
- [x] 4.2 Исправить навигацию support chat detail, чтобы не пропадал sidebar
- [x] 4.3 Убрать зависимость от Google Fonts и зафиксировать стабильную production build команду

## 5. Verification

- [x] 5.1 Прогнать `pnpm --dir frontend lint`
- [x] 5.2 Прогнать `pnpm --dir frontend typecheck`
- [x] 5.3 Прогнать `pnpm --dir frontend build`
- [x] 5.4 Проверить live backend smoke-flow: `/health`, `/chat`, `/api/documents`, upload/detail/reindex/delete через frontend proxy
