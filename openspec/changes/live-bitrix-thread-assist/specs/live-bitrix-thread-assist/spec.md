## Purpose

Пассивный ассистент в живом треде поддержки Bitrix: на сообщение пользователя готовит черновик оператору (draft) или отвечает пользователю напрямую (auto), переиспользуя общий RAG-граф и runtime-настройки.

## ADDED Requirements

### Requirement: Режим assist в живом треде — единое runtime-значение

The system SHALL decide live-thread behavior per event from the effective operator assist mode (`draft` or `auto`) as returned by the runtime settings mechanism (`PUT /api/settings` override over the environment default). Two consecutive events processed with different effective modes SHALL follow the new mode without a process restart.

#### Scenario: Draft переключается на auto без рестарта

- **WHEN** the effective mode is changed from `draft` to `auto` through `PUT /api/settings` and then a new user thread message is processed
- **THEN** the message is handled as `auto` (potential reply to the user) even though earlier messages in the same thread were handled as `draft`

#### Scenario: Default mode is draft

- **WHEN** no runtime override exists and the environment default is `draft`
- **THEN** a user thread message produces a draft for the operator, not a reply to the user

### Requirement: Draft-режим готовит черновик оператору

In `draft` mode, a `user` message in the thread SHALL run retrieval and generation over the message and history, store the generated text in `suggested_response`, and SHALL NOT send that text to the user. The conversation status SHALL NOT change as a result of processing the message. The draft SHALL be returned in the webhook response for delivery to the operator.

#### Scenario: User message yields operator draft

- **WHEN** a user message is processed in draft mode
- **THEN** `suggested_response` holds generated text, the transcript does not contain an assistant message for it, and the webhook response returns the draft text

#### Scenario: Draft does not escalate

- **WHEN** retrieval for a draft-mode message scores below the confidence threshold
- **THEN** the draft is still generated and returned, and the conversation stays non-escalated

### Requirement: Auto-режим отвечает пользователю или эскалирует

In `auto` mode, a `user` message in the thread SHALL run the same RAG graph as scenario 1. When retrieval confidence is at or above the effective threshold, the generated answer SHALL be persisted as an assistant message in the conversation and returned for delivery to the user in the same thread. When confidence is below the threshold, the system SHALL escalate: persist the guest escalation phrase, create an `Escalation` row, transition the conversation to `escalated`, and return the escalation outcome.

#### Scenario: Auto mode answers the user

- **WHEN** a user message is processed in auto mode and confidence is at or above the threshold
- **THEN** an assistant message with the generated answer exists in the conversation and the webhook response returns the reply text for the user

#### Scenario: Auto mode escalates on low confidence

- **WHEN** a user message is processed in auto mode and confidence is below the threshold
- **THEN** the conversation becomes `escalated`, an `Escalation` row exists, the transcript contains the guest escalation phrase, and no generated answer is produced

#### Scenario: Repeated message does not re-run auto

- **WHEN** a duplicate user message is retried in auto mode
- **THEN** the agent graph is not run again and no second reply or escalation is created

### Requirement: Сообщение оператора не активирует агента

A message from the `operator` SHALL be persisted in the transcript and SHALL NOT run the RAG graph, SHALL NOT change `suggested_response`, and SHALL NOT create a draft, reply or escalation.

#### Scenario: Operator message leaves draft unchanged

- **WHEN** an operator message is processed while a previously generated draft exists
- **THEN** the draft stays as-is and no assistant activity occurs