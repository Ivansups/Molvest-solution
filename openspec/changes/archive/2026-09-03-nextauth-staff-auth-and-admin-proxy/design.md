## Context

ТЗ требует два независимых пользовательских контура:

- гостевой web-chat без логина;
- закрытая support-консоль для сотрудников.

Next.js может валидировать staff-сессию, но FastAPI не должен разбирать
cookie `NextAuth`, иначе backend начнёт зависеть от frontend-реализации
аутентификации. Поэтому boundary проходит так: staff auth живёт во frontend,
а backend доверяет только внутреннему сервисному токену на admin-ручках.

## Goals / Non-Goals

**Goals:**

- Перевести вход сотрудников на `NextAuth Credentials` + `Prisma`.
- Хранить auth-данные в отдельном наборе таблиц в той же Postgres.
- Защитить support-маршруты через server-side проверку staff-сессии.
- Оставить `/chat` публичным.
- Направить admin-вызовы через Next server hop с `INTERNAL_SERVICE_TOKEN`.
- Убрать двойной auth-контур из legacy HMAC/mock flow.

**Non-Goals:**

- Ответ оператора в guest chat в реальном времени.
- Bitrix, SSE, tRPC и отдельный auth backend для сотрудников.
- Передача `INTERNAL_SERVICE_TOKEN` в браузер или прямой browser-доступ к
  admin-ручкам FastAPI.

## Decisions

### D1. Staff auth живёт только во frontend

`NextAuth` с `Credentials` и `PrismaAdapter` становится единственным способом
входа сотрудников. FastAPI не знает о cookie `NextAuth` и не проверяет их.

- Альтернатива: парсить `NextAuth` cookie на FastAPI. Отвергнута, потому что
  это смешивает frontend auth и backend domain auth.

### D2. Отдельные auth-таблицы в той же Postgres

Prisma управляет только `User`, `Account`, `Session`, `VerificationToken`.
Таблицы получают собственные имена (`auth_users`, `auth_sessions`, ...), чтобы
не пересекаться с Alembic-моделями домена.

### D3. Публичный chat и закрытая console разделяются по маршрутам

`/chat` и его гостевой UX остаются публичными. Support-консоль живёт в
защищённой route group и при отсутствии staff-сессии редиректит на `/login`.

### D4. Admin API вызывается только с Next-сервера

Для операций документов и следующих внутренних API frontend использует Next
route handlers / server actions. Они:

1. Проверяют staff-сессию через `NextAuth`.
2. Подставляют `installation_id` и другие служебные поля.
3. Добавляют `X-Internal-Token` или эквивалентный служебный заголовок.
4. Форвардят запрос в FastAPI.

Browser не получает значение токена и не вызывает admin-ручки напрямую.

### D5. Service token нужен только admin-ручкам

`INTERNAL_SERVICE_TOKEN` проверяется на `/api/documents` и следующих
внутренних read/write API консоли. `POST /chat` для guest-сценария остаётся
публичным и не должен ломаться от отсутствия staff auth.

### D6. Legacy HMAC/mock flow выводится из сценария

Старые helpers и HMAC-cookie не должны оставаться вторым живым способом входа,
иначе система получает два несогласованных контура с разными правилами ролей и
протухшими тестами.

## Risks / Trade-offs

- [Frontend auth зависит от auth-БД] → server-side чтение сессии должно быть
  безопасно для build/runtime и не ломать публичные маршруты.
- [Admin proxy разрастается] → держать его узким: только auth check, служебные
  заголовки и проксирование, без доменной логики.
- [Guest и staff-сценарии пересекаются в UI] → boundary фиксируется маршрутами
  и разными API hop'ами.

## Migration Plan

1. Применить Prisma migration для auth-таблиц в `frontend/`.
2. Выполнить Prisma seed с демо-пользователями.
3. Подключить `NEXTAUTH_SECRET`, `AUTH_DATABASE_URL` и
   `INTERNAL_SERVICE_TOKEN`.
4. Перевести support UI на `NextAuth`-сессию.
5. Переключить admin browser-calls на Next route handlers.
6. На backend включить проверку `INTERNAL_SERVICE_TOKEN` только на admin-API.

## Open Questions

- Нужны ли отдельные role-based ограничения между `admin` и `operator` сверх
  доступа к `/operator`.
- Когда `/api/conversations` и `/api/metrics` будут окончательно включены в
  тот же admin-token контур.
