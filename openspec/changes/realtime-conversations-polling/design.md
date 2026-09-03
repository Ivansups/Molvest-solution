## Context

Панель оператора (`frontend/src/components/pages/chat-page.tsx`) получает список диалогов через React Query, но `chatService.listConversations()` и `getConversation()` — заглушки с `unsupportedEndpoint`. Бэкенд уже публикует `GET /api/conversations` и `GET /api/conversations/{id}` (Этап 6). Данные в `chat-page.tsx` имеют статический макетный тип `ConversationPreview`/`ConversationDetail`, не совпадающий с реальным `ConversationOut`/`ConversationDetailOut` с бэкенда. См. proposal.md — Why.

## Goals / Non-Goals

**Goals:**
- Связать список и детали диалогов с реальными бэкенд-эндпоинтами
- Автообновление списка через поллинг `refetchInterval`
- Адаптировать при рендере под реальный формат данных

**Non-Goals:**
- WebSocket / SSE канал — выбран самый дешёвый вариант (поллинг)
- Изменения на бэкенде — API уже готово
- Инвалидация в момент отправки сохраняется как дополнительный механизм

## Decisions

**Выбор поллинга вместо WebSocket/SSE.** Задача предлагает два варианта: дешёвый поллинг через `refetchInterval` и честный realtime (WebSocket/SSE). Выбран поллинг — минимальные изменения, одно место правки, простой откат. WebSocket/SSE требует нового канала на бэкенде и инфраструктуры, что выходит за рамки устранения пробела из ROADMAP §12.

**Частота поллинга 5 секунд.** Компромисс между свежестью списка и нагрузкой на `GET /api/conversations`. Для сценария поддержки в реальном времени 5 секунд достаточно, чтобы оператор не пропустил эскалацию.

**Адаптация типов через маппинг.** Вместо переписывания всего UI под snake_case бэкенд-формат, сохраняется существующий camelCase-тип `ConversationPreview`/`ConversationDetail` на фронте, а маппинг бэкенд→фронт выполняется в `chatService`. Это минимизирует изменения в `chat-page.tsx`.

## Risks / Trade-offs

- **Нагрузка поллинга** → Интервал 5 секунд и малый размер списка; при росте можно увеличить интервал или перейти на SSE.
- **Бэкенд требует `installation_id`** → Использовать `DEFAULT_INSTALLATION_ID`/`user.installationId`, как в `sendMessage`.
- **404 для несуществующего диалога** → `getConversation` возвращает `null`, селектор уже обрабатывает `null`.
