## ADDED Requirements

### Requirement: Гостевой диалог сохраняется в пределах вкладки

После первого `POST /chat` frontend SHALL сохранять возвращённый
`conversation_id` в `sessionStorage` под ключом `guest_conversation_id` и
использовать его для последующих запросов в этой вкладке.

#### Scenario: Перезагрузка гостевого чата

- **WHEN** гость обновляет страницу после успешного ответа backend
- **THEN** frontend загружает сохранённый диалог и отображает его историю

#### Scenario: Новая вкладка гостя

- **WHEN** гость открывает чат в другой вкладке без сохранённого ID
- **THEN** первый `POST /chat` не передаёт `conversation_id` и backend создаёт диалог
