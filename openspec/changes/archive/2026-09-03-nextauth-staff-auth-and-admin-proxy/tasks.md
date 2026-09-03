## 1. Staff auth на NextAuth + Prisma

- [x] 1.1 Добавить `NextAuth Credentials` + `PrismaAdapter` во `frontend/` и
  завести отдельные auth-таблицы в `prisma/schema.prisma`. Проверить: сборка
  frontend проходит, auth route зарегистрирован.
- [x] 1.2 Добавить Prisma seed с demo-учётками `admin@molvest.ru` и
  `operator@molvest.ru`, убрать режим "любой пароль". Проверить: demo users
  описаны в auth-helpers и seed.
- [x] 1.3 Убрать legacy HMAC/mock auth из целевого flow. Проверить: support
  login больше не зависит от старых fake session helpers.

## 2. Защита support console

- [x] 2.1 Защитить `(console)` route group server-side проверкой staff-сессии.
  Проверить: без сессии console routes редиректят на `/login`.
- [x] 2.2 Оставить `/chat` публичным и не требующим staff login. Проверить:
  `/chat` рендерится без сессии.
- [x] 2.3 Сохранить существующий UI shell и экранные артефакты main-ветки.
  Проверить: `/login` и `/chat` рендерятся без поломки shell/layout.

## 3. Server-side admin hop

- [x] 3.1 Добавить Next route handlers / server helpers для admin document API.
  Проверить: browser код работает через `/api/admin/*`, а не напрямую через
  FastAPI admin route.
- [x] 3.2 Проксировать admin-вызовы только после проверки staff-сессии и
  добавлять `INTERNAL_SERVICE_TOKEN` только на серверном hop. Проверить: token
  не нужен в клиентском bundle и не передаётся из браузера.

## 4. OpenSpec sync

- [x] 4.1 Обновить живые `openspec/specs/*` под целевой auth/admin boundary.
- [x] 4.2 Создать archived change с proposal/design/tasks/spec deltas.
