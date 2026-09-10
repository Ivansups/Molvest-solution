## 1. OpenSpec и контракт

- [x] 1.1 Зафиксировать в proposal проблему ручного обновления и область
  frontend-only изменений.
- [x] 1.2 Описать в design решение с динамическим React Query interval,
  ограничениями и рисками.
- [x] 1.3 Сформулировать требования и сценарии polling для списка и карточки.

## 2. Polling списка базы знаний

- [x] 2.1 Добавить динамический `refetchInterval` 4 секунды, пока в текущих
  `items` есть `PENDING`.
- [x] 2.2 Проверить остановку interval после `INDEXED`/`FAILED` на уровне
  callback React Query.

## 3. Polling карточки документа

- [x] 3.1 Добавить динамический `refetchInterval` 4 секунды, пока документ
  имеет `PENDING`, сохранив `enabled` для `docId`.
- [x] 3.2 Отобразить актуальный `status` в заголовке карточки.

## 4. Проверка качества

- [x] 4.1 Выполнить `pnpm --dir frontend lint`.
- [x] 4.2 Выполнить `pnpm --dir frontend typecheck`.
- [x] 4.3 Выполнить frontend-тесты `pnpm --dir frontend test`.
- [x] 4.4 Выполнить `git diff --check` и проверить OpenSpec change.
