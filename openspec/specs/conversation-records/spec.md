## Purpose

Persist conversations, messages, and escalations from `POST /chat`, and expose read-only conversation and metrics APIs for the admin console. Status may change only through the transition service.

## Requirements

### Requirement: Conversation tables exist

The system SHALL persist Conversation, Message, and Escalation rows in PostgreSQL with the fields defined in roadmap Stage 2, plus nullable `Conversation.suggested_response`. Conversation.status SHALL be one of `open`, `escalated`, `resolved`. Message.role SHALL be one of `user`, `assistant`, `system`, `operator`. Timestamps SHALL be stored in UTC. Alembic SHALL add `suggested_response` with a named column on `conversations`.

#### Scenario: Migration creates conversation tables

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Conversation, Message, and Escalation tables exist with the expected columns including `suggested_response`

### Requirement: Status changes only through the transition service

The system SHALL change `Conversation.status` only through a single transition service. Allowed transitions are `open → escalated` and `escalated → resolved`. Any other assignment, including direct writes from a router or graph node, is out of contract. An illegal transition SHALL raise a domain error and SHALL NOT persist.

#### Scenario: Legal escalation

- **WHEN** the transition service is asked to move a conversation from `open` to `escalated`
- **THEN** the stored status becomes `escalated`

#### Scenario: Illegal skip

- **WHEN** the transition service is asked to move a conversation from `open` to `resolved`
- **THEN** the call fails and the stored status stays `open`

#### Scenario: Illegal backward move

- **WHEN** the transition service is asked to move a conversation from `escalated` to `open`
- **THEN** the call fails and the stored status stays `escalated`

### Requirement: Chat persists user and assistant messages

The system SHALL persist every `POST /chat` turn: when `conversation_id` is absent, SHALL create a `Conversation` with status `open`; SHALL write a `Message` with role `user` (the incoming text). When the turn is a guest-facing auto-answer, SHALL also write a `Message` with role `assistant` carrying `content`, `confidence`, `sources`, and `escalated=false`. When the turn is a first escalation, SHALL write a `Message` with role `system` carrying the guest escalation phrase and SHALL NOT fill `suggested_response`. When the turn is a guest follow-up on an already `escalated` conversation in `draft` mode, SHALL NOT write an assistant or extra system message and SHALL NOT change `suggested_response`. User and any guest-facing message SHALL be committed in one transaction. Bitrix and Redmine channel escalations MAY fill `suggested_response` after that commit per `bitrix-escalation-handoff`.

#### Scenario: New conversation is created

- **WHEN** a client calls `POST /chat` without `conversation_id`
- **THEN** a `Conversation` row with status `open` and both user and assistant `Message` rows exist, and the response echoes the created `conversation_id`

#### Scenario: Existing conversation appends

- **WHEN** a client calls `POST /chat` with an existing `open` conversation_id and the graph does not escalate
- **THEN** the user and assistant messages are appended to that conversation and no new conversation row is created

#### Scenario: Draft follow-up does not add assistant text

- **WHEN** a client calls `POST /chat` on an already `escalated` conversation in `draft` mode
- **THEN** only the new user message is appended as a chat message and `suggested_response` is unchanged

### Requirement: Escalation is persisted and surfaced

The system SHALL, when the graph returns `escalated=true` on an `open` conversation, change the conversation status `open → escalated` only via the transition service and create one `Escalation` row with `conversation_id`, `message_id`, `reason`, and `escalated_to`. The `reason` SHALL reflect the source of escalation: a weak retrieval score or an explicit guest request to hand off to a human. The HTTP response SHALL carry `escalated=true` and the guest-facing escalation phrase. On `POST /chat`, `suggested_response` SHALL stay empty until an operator suggest call. On Bitrix and Redmine channel turns, `suggested_response` SHALL be filled after commit per `bitrix-escalation-handoff`. Replaying the same escalating turn (weak score or explicit handoff) SHALL NOT create a second `Escalation` row, and SHALL NOT downgrade an already `escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the threshold via `POST /chat`
- **THEN** the conversation status becomes `escalated`, one `Escalation` row exists with a weak-score reason, `suggested_response` is empty, generate was not called, and the response has `escalated=true` with the guest escalation phrase

#### Scenario: Explicit handoff escalates with its own reason

- **WHEN** a client sends «позовите оператора»
- **THEN** the conversation status becomes `escalated`, one `Escalation` row exists with a handoff reason, generate was not called, and the response has `escalated=true` with the guest escalation phrase

#### Scenario: Replay does not double-escalate

- **WHEN** the same weak-scoring turn is sent twice against the same conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the status stays `escalated`

#### Scenario: Handoff replay does not double-escalate

- **WHEN** the same explicit handoff request is sent twice against the same conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the status stays `escalated`

### Requirement: List conversations

The system SHALL provide `GET /api/conversations` returning a paginated list. The system SHALL support pagination parameters `page` and `page_size`, and optional filters by `date` (range), `user_id`, and `status` (including `escalated`). Responses SHALL include conversation metadata so the admin console can render the list.

#### Scenario: List with status filter

- **WHEN** a client requests `GET /api/conversations` with `status=escalated`
- **THEN** the API returns only escalated conversations for the installation, with pagination metadata

#### Scenario: List with user filter

- **WHEN** a client requests the list filtered by a `user_id`
- **THEN** the API returns only conversations of that user for the installation

### Requirement: Conversation details

The system SHALL provide `GET /api/conversations/{id}` returning the conversation, `suggested_response` (nullable string), its messages with `role` (including `operator`), `content`, `confidence`, `escalated`, and `sources`, and escalations. An unknown id SHALL return 404.

#### Scenario: Get details

- **WHEN** a client fetches an existing conversation id
- **THEN** the API returns the conversation with its messages, escalation records, and `suggested_response`

#### Scenario: Missing conversation

- **WHEN** a client fetches an unknown conversation id
- **THEN** the API returns 404

### Requirement: Conversation metrics

The system SHALL provide `GET /api/metrics` returning the percent of auto-answered messages (those not escalated), the average response time in seconds, and the count of escalations over the requested period.

#### Scenario: Metrics returned

- **WHEN** a client requests `GET /api/metrics`
- **THEN** the API returns auto-answer percent, average response time, and escalation count based on persisted conversations and messages

### Requirement: Resolved conversations reject new guest turns

The system SHALL reject `POST /chat` with `conversation_id` pointing to a `resolved` conversation in that installation. The response SHALL be 409. No new message SHALL be stored.

#### Scenario: Guest cannot continue a resolved ticket

- **WHEN** a client sends `POST /chat` with a `resolved` conversation_id
- **THEN** the API returns 409 and the message list is unchanged
