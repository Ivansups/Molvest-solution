## Why

Список диалогов в панели оператора не обновляется автоматически. Если оператор просто читает список, новая эскалация от гостя не появится — нужен ручной рефреш страницы. При одновременной эскалации нескольких диалогов оператор узнаёт об этом только после действия на странице.

## What Changes

- Добавить `refetchInterval` на React Query запрос списка диалогов (`conversationsQuery`) — поллинг каждые 5 секунд
- Реализовать `chatService.listConversations()` и `chatService.getConversation()` — они сейчас являются заглушками с `unsupportedEndpoint`
- Адаптировать фронтенд-типы `ConversationPreview` и `ConversationDetail` к реальному бэкенд-формату `ConversationOut` / `ConversationDetailOut`
- Обновить UI-компоненты (список диалогов, карточка диалога) под реальные данные из API

## Capabilities

### New Capabilities
- `realtime-conversations-polling`: Автоматическое обновление списка диалогов через поллинг для панели оператора

### Modified Capabilities

## Impact

- `frontend/src/services/chat-service.ts` — реализация API-вызовов
- `frontend/src/types/domain.ts` — адаптация типов под бэкенд
- `frontend/src/components/pages/chat-page.tsx` — добавление `refetchInterval`, адаптация UI под реальные данные
