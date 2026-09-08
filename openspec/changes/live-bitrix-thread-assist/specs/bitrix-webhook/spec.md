## Purpose

Приём входящих сообщений живого треда поддержки Bitrix: webhook-контракт, классификация отправителя, привязка id треда канала к внутреннему `conversation_id` и идемпотентная обработка повторных событий.

## ADDED Requirements

### Requirement: Webhook принимает сообщения живого треда

The system SHALL expose `POST /webhook/bitrix` that accepts a workspace, a channel thread id, a channel message id, a sender (`user` or `operator`), optional text, and an optional channel user id. On each event the system SHALL return the internal `conversation_id`, a processing status, and any output the agent produced for that event. The webhook SHALL be protected by the same internal service token as other admin APIs.

#### Scenario: Incoming user message creates a conversation

- **WHEN** a `user` message arrives at the webhook for a thread id not seen before
- **THEN** the system creates an `open` conversation, persists the message with role `user`, links the channel thread id to the conversation id, and returns that conversation id with status `processed`

#### Scenario: Incoming operator message continues the thread

- **WHEN** an `operator` message arrives in an already-linked thread
- **THEN** the system persists the message with role `operator` in the same conversation without starting the agent graph, and returns status `processed`

#### Scenario: Sender is neither user nor operator

- **WHEN** a webhook event carries an unsupported sender value
- **THEN** the system responds with a validation error and persists nothing

### Requirement: Маппинг «id треда канала → conversation_id»

The system SHALL keep a unique mapping from `(channel, thread_id, installation_id)` to `conversation_id`. The first message of a thread SHALL create the mapping; all later messages SHALL reuse the same conversation. A thread from another installation SHALL NOT resolve to a conversation of this installation.

#### Scenario: Later thread messages reuse the conversation

- **WHEN** a second message arrives in a thread whose first message created a conversation
- **THEN** the message is persisted in that same conversation and the mapping is not duplicated

#### Scenario: Same thread id in another installation

- **WHEN** a thread id is linked to a conversation in one installation and a message with the same thread id arrives for another installation
- **THEN** the second installation gets its own new conversation

### Requirement: Повтор события не дублируется

The system SHALL record each processed `(channel, message_id)` and SHALL treat a repeated event with the same `channel` and `message_id` as a duplicate: it SHALL NOT persist another message, SHALL NOT run the agent graph, SHALL NOT create a draft or escalation, and SHALL respond with status `duplicate`.

#### Scenario: Webhook retry is idempotent

- **WHEN** the same `user` message id is delivered to the webhook a second time after a successful first processing
- **THEN** the conversation, messages, drafts and escalations are unchanged and the response has status `duplicate`

#### Scenario: Retry of an operator message

- **WHEN** the same `operator` message id is delivered twice
- **THEN** the transcript contains exactly one operator message and the second response has status `duplicate`