## 1. Чтение диалогов с бэкенда

- [x] 1.1 Реализовать `chatService.listConversations()` — запрос `GET /api/conversations?installation_id=...`, маппинг в `ConversationPreview[]`; проверить `pnpm --dir frontend typecheck`
- [x] 1.2 Реализовать `chatService.getConversation()` — запрос `GET /api/conversations/{id}?installation_id=...`, возврат `ConversationDetail | null` при 404; проверить `pnpm --dir frontend typecheck`
- [x] 1.3 Расширить `chatService` вспомогательными мапперами бэкенд (`ConversationOut`/`MessageOut`) → фронт-типы; проверить отсутствие ошибок типов

## 2. Поллинг списка диалогов

- [x] 2.1 Добавить `refetchInterval: 5_000` в `conversationsQuery` в `chat-page.tsx`; проверить, что список автообновляется при рендере без действий оператора

## 3. Адаптация UI под реальные данные

- [x] 3.1 Обновить `ConversationPreview`/`ConversationDetail`/`ConversationMessage` в `type/domain.ts` под бэкенд-формат; проверить `pnpm --dir frontend typecheck`
- [x] 3.2 Адаптировать рендер списка и карточки диалога в `chat-page.tsx` под реальные поля; проверить `pnpm --dir frontend lint && typecheck`
