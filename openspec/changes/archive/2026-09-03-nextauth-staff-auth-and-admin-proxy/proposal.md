## Why

Во frontend оставался временный контур входа: mock-логин принимал любой пароль,
роль вычислялась только по email, а защищённые маршруты опирались на локальную
сессию. Параллельно admin-API вызывался браузером через общий `/backend`
proxy, поэтому backend не мог отличить гостевой публичный чат от внутренних
операций сотрудников.

Для хакатонного ТЗ этого недостаточно. Нужен единый целевой контур:
сотрудники входят через `NextAuth` и `Prisma`, guest `/chat` остаётся публичным,
а внутренние admin-вызовы идут только через Next-сервер с
`INTERNAL_SERVICE_TOKEN`. FastAPI не разбирает cookie `NextAuth` и не зависит
от frontend-сессии.

## What Changes

- **Сотрудники**: support login переходит на `NextAuth Credentials` +
  `PrismaAdapter` в `frontend/`; пользователи и сессии хранятся в отдельных
  auth-таблицах Postgres без пересечения с доменной схемой Alembic.
- **Демо-учётки**: seed создаёт `admin@molvest.ru` и `operator@molvest.ru` с
  фиксированными паролями, вместо режима "любой email + пароль".
- **Маршруты**: `/`, `/knowledge-base`, `/settings`, `/analytics`,
  `/operator`, `/chat/support`, `/chat/support/:ticketId` требуют staff-сессию
  и редиректят на `/login`. `/chat` остаётся публичным.
- **Admin API**: browser больше не ходит на FastAPI admin-ручки напрямую через
  `/backend`. Для документов и следующих внутренних разделов используются
  Next route handlers / server actions, которые после проверки `NextAuth`
  добавляют `INTERNAL_SERVICE_TOKEN`.
- **Backend contract**: FastAPI принимает `INTERNAL_SERVICE_TOKEN` только на
  admin-ручках (`/api/documents`, далее `/api/conversations`, `/api/metrics`);
  публичный guest chat не требует staff-сессии и не использует cookie
  `NextAuth`.
- **Очистка legacy**: старый HMAC/mock auth-контур (`molvest-user`,
  `SESSION_SECRET`, локальные fake helpers) выводится из целевого сценария.

## Capabilities

### New Capabilities

- `support-staff-auth`: staff-сессии на `NextAuth` + `Prisma` с демо-учётками,
  хранением сессий в Postgres и server-side защитой support-консоли.

### Modified Capabilities

- `support-console-ui`: защищённые маршруты ведут на `/login`, а не на
  гостевой `/chat`.
- `frontend-runtime-integration`: guest traffic продолжает идти через
  `/backend`, но admin-функции документов и следующих внутренних API идут через
  Next server handlers.
- `service-to-service-auth`: `INTERNAL_SERVICE_TOKEN` обязателен только для
  admin-API и никогда не попадает в browser bundle.

## Impact

- `frontend/auth.ts`, `frontend/app/api/auth/[...nextauth]/route.ts`,
  `frontend/prisma/*` — staff auth и seed.
- `frontend/app/(console)/*`, `frontend/src/lib/session.ts` — защита console
  маршрутов через staff-сессию.
- `frontend/app/api/admin/*`, `frontend/src/lib/admin-api.ts` — server-side hop
  для admin-API.
- `openspec/specs/support-staff-auth/spec.md` — новая capability.
- `openspec/specs/support-console-ui/spec.md`,
  `openspec/specs/frontend-runtime-integration/spec.md`,
  `openspec/specs/service-to-service-auth/spec.md` — уточнение целевого
  контракта между guest chat, support console и admin API.
