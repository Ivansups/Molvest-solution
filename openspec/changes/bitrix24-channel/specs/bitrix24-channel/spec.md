## Purpose

Реальная интеграция портала Bitrix24 по сценарию 1: приём входящих сообщений открытой линии с валидацией токена приложения, связывание id сессии открытой линии с внутренним `conversation_id` и отправка ответа агента в тот же диалог через REST.

## ADDED Requirements

### Requirement: Входящий webhook открытой линии принимает события портала

The system SHALL expose an inbound webhook for Bitrix24 Open Lines events. Each event SHALL carry an Open Lines session (dialog) id, a channel author id, a channel message id, optional text, and an optional file or image attachment reference. The system SHALL authenticate the event with the Bitrix application token and SHALL reject events without a valid token with HTTP 403 and without changing any state. For each accepted event the system SHALL persist the guest or operator message and SHALL respond with the internal `conversation_id`, a processing status, and any output the agent produced, or a validation error for unsupported event shapes.

#### Scenario: Первое сообщение гостя создаёт диалог

- **WHEN** an Open Lines event from a guest with a valid application token arrives for a session id not seen before
- **THEN** the system creates an `open` conversation, persists the message with role `user`, links the session id to the conversation id, and returns that conversation id with status `processed`

#### Scenario: Неверный токен приложения отклоняется

- **WHEN** an Open Lines event arrives with a missing or invalid application token
- **THEN** the system responds with HTTP 403 and persists nothing

#### Scenario: Событие с файлом или картинкой

- **WHEN** an accepted event carries an image attachment reference
- **THEN** the message is processed with the image available to the agent pipeline, and no attachment text is required for processing

### Requirement: Маппинг «id диалога открытой линии → conversation_id»

The system SHALL keep a unique mapping from the Open Lines session id to `conversation_id` scoped per portal installation. The first message of a session SHALL create the mapping; all later messages of that session SHALL reuse the same conversation. Two different sessions SHALL resolve to two different conversations, and a session of one portal installation SHALL NOT resolve to a conversation of another installation.

#### Scenario: Следующие сообщения сессии продолжают диалог

- **WHEN** a new message arrives in a session whose first message created a conversation
- **THEN** the message is persisted in that same conversation and no new mapping or conversation is created

#### Scenario: Одна и та же сессия на другом портале

- **WHEN** a session id is linked to a conversation on one portal and a message with the same session id arrives for another portal installation
- **THEN** the second portal gets its own new conversation

### Requirement: Повтор события не дублируется

The system SHALL treat a repeated delivery of the same channel message id as a duplicate: it SHALL NOT persist another message, SHALL NOT run the agent graph, SHALL NOT create a draft, reply or escalation, and SHALL respond with status `duplicate`.

#### Scenario: Повторная доставка webhook идемпотентна

- **WHEN** the same guest message id is delivered to the webhook a second time after a successful first processing
- **THEN** the conversation, messages, drafts and escalations are unchanged and the response has status `duplicate`

#### Scenario: Повторное событие не шлёт ответ повторно

- **WHEN** a message id that already produced a delivered reply is retried
- **THEN** the system does not send the reply to the portal again and responds with status `duplicate`

### Requirement: Ответ агента возвращается в тот же диалог открытой линии

When processing a guest message produces a reply for the guest, the system SHALL deliver that reply text into the same Open Lines dialog of the same portal installation through the Bitrix REST API. Delivery SHALL happen only after the conversation state is committed. When processing produces no reply — draft for the operator, an operator message, or an escalation — the system SHALL NOT send a generated answer to the dialog and SHALL return the corresponding outcome instead.

#### Scenario: Автоответ уходит в тот же диалог

- **WHEN** a guest message is processed in auto mode with confidence at or above the threshold
- **THEN** the generated answer is persisted as an assistant message and, after commit, delivered back into the same Open Lines session

#### Scenario: Эскалация ничего не отправляет пользователю

- **WHEN** a guest message is processed with confidence below the threshold
- **THEN** the conversation becomes `escalated` and no generated answer is sent to the dialog

#### Scenario: Сообщение оператора не активирует исходящую отправку

- **WHEN** an operator message is processed in a linked session
- **THEN** the transcript gains a single `operator` message and no reply is sent to the dialog

### Requirement: Секреты Bitrix — только через окружение

The system SHALL read the portal URL, application user id and application token exclusively from the environment (`BITRIX_*`). These values SHALL NOT be accepted via the API or settings endpoints, SHALL NOT be persisted in the database, and SHALL NOT appear in HTTP responses or log output. Log entries for outbound REST calls SHALL NOT contain the token.

#### Scenario: Токен не возвращается в ответе

- **WHEN** any inbound webhook or settings API response is produced
- **THEN** the response body contains no Bitrix portal URL, user id or application token

#### Scenario: Токен не пишется в логи

- **WHEN** the system logs an inbound event or an outbound REST delivery attempt
- **THEN** the log line contains no application token