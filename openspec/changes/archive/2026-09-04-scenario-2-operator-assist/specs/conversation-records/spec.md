## MODIFIED Requirements

### Requirement: Conversation tables exist

The system SHALL persist Conversation, Message, and Escalation rows in PostgreSQL with the fields defined in roadmap Stage 2, plus nullable `Conversation.suggested_response`. Conversation.status SHALL be one of `open`, `escalated`, `resolved`. Message.role SHALL be one of `user`, `assistant`, `system`, `operator`. Timestamps SHALL be stored in UTC. Alembic SHALL add `suggested_response` with a named column on `conversations`.

#### Scenario: Migration creates conversation tables

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Conversation, Message, and Escalation tables exist with the expected columns including `suggested_response`

### Requirement: Chat persists user and assistant messages

The system SHALL persist every `POST /chat` turn: when `conversation_id` is absent, SHALL create a `Conversation` with status `open`; SHALL write a `Message` with role `user` (the incoming text). When the turn is a guest-facing auto-answer, SHALL also write a `Message` with role `assistant` carrying `content`, `confidence`, `sources`, and `escalated=false`. When the turn is a first escalation, SHALL write a `Message` with role `system` carrying the guest escalation phrase and SHALL NOT fill `suggested_response`. When the turn is a guest follow-up on an already `escalated` conversation in `draft` mode, SHALL NOT write an assistant or extra system message and SHALL NOT change `suggested_response`. User and any guest-facing message SHALL be committed in one transaction.

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

The system SHALL, when the graph returns `escalated=true` on an `open` conversation, change the conversation status `open → escalated` only via the transition service and create one `Escalation` row with `conversation_id`, `message_id`, `reason`, and `escalated_to`. The HTTP response SHALL carry `escalated=true` and the guest-facing escalation phrase. `suggested_response` SHALL stay empty until an operator suggest call. Replaying the same weak-scoring turn SHALL NOT create a second `Escalation` row, and SHALL NOT downgrade an already `escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the threshold
- **THEN** the conversation status becomes `escalated`, one `Escalation` row exists, `suggested_response` is empty, generate was not called, and the response has `escalated=true` with the guest escalation phrase

#### Scenario: Replay does not double-escalate

- **WHEN** the same weak-scoring turn is sent twice against the same conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the status stays `escalated`

### Requirement: Conversation details

The system SHALL provide `GET /api/conversations/{id}` returning the conversation, `suggested_response` (nullable string), its messages with `role` (including `operator`), `content`, `confidence`, `escalated`, and `sources`, and escalations. An unknown id SHALL return 404.

#### Scenario: Get details

- **WHEN** a client fetches an existing conversation id
- **THEN** the API returns the conversation with its messages, escalation records, and `suggested_response`

#### Scenario: Missing conversation

- **WHEN** a client fetches an unknown conversation id
- **THEN** the API returns 404

## ADDED Requirements

### Requirement: Resolved conversations reject new guest turns

The system SHALL reject `POST /chat` with `conversation_id` pointing to a `resolved` conversation in that installation. The response SHALL be 409. No new message SHALL be stored.

#### Scenario: Guest cannot continue a resolved ticket

- **WHEN** a client sends `POST /chat` with a `resolved` conversation_id
- **THEN** the API returns 409 and the message list is unchanged
