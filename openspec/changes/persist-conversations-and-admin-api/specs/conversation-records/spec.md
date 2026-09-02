## REMOVED Requirements

### Requirement: No public conversation API

**Reason**: Этап 6 требует read-only доступа к диалогам и метрикам для админки; persist диалогов включается в работу `POST /chat`.
**Migration**: Вместо запрета появляются `GET /api/conversations`, `GET /api/conversations/{id}` и `GET /api/metrics`. `POST /chat` обязан персистить диалог.

## MODIFIED Requirements

### Requirement: Conversation tables exist

The system SHALL persist Conversation, Message, and Escalation rows in PostgreSQL with the fields defined in roadmap Stage 2. Conversation.status SHALL be one of `open`, `escalated`, `resolved`. Message.role SHALL be one of `user`, `assistant`, `system`. Timestamps SHALL be stored in UTC. The first Alembic revision SHALL create these tables with named indexes and foreign keys.

#### Scenario: Migration creates conversation tables

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Conversation, Message, and Escalation tables exist with the expected columns

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

## ADDED Requirements

### Requirement: Chat persists user and assistant messages

The system SHALL persist every `POST /chat` turn: when `conversation_id` is absent, SHALL create a `Conversation` with status `open`; SHALL write a `Message` with role `user` (the incoming text) and, unless the graph finished with an empty answer, a `Message` with role `assistant` or `system` carrying `content`, `confidence`, `sources`, and `escalated`. The user message and the assistant message SHALL be committed in one transaction.

#### Scenario: New conversation is created

- **WHEN** a client calls `POST /chat` without `conversation_id`
- **THEN** a `Conversation` row with status `open` and both user and assistant `Message` rows exist, and the response echoes the created `conversation_id`

#### Scenario: Existing conversation appends

- **WHEN** a client calls `POST /chat` with an existing `conversation_id`
- **THEN** the user and assistant messages are appended to that conversation and no new conversation row is created

### Requirement: Escalation is persisted and surfaced

The system SHALL, when the graph returns `escalated=true`, change the conversation status `open → escalated` only via the transition service and create one `Escalation` row with `conversation_id`, `message_id`, `reason`, and `escalated_to`. The HTTP response SHALL carry `escalated=true` and a non-empty guest-facing text explaining the case was handed to an operator. Replaying the same weak-scoring turn SHALL NOT create a second `Escalation` row, and SHALL NOT downgrade an already `escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the threshold
- **THEN** the conversation status becomes `escalated`, one `Escalation` row exists, and the response has `escalated=true` with non-empty text and no generated answer

#### Scenario: Replay does not double-escalate

- **WHEN** the same weak-scoring turn is sent twice against the same conversation
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

The system SHALL provide `GET /api/conversations/{id}` returning the conversation, its messages with `role`, `content`, `confidence`, `escalated`, and `sources`, and escalations. An unknown id SHALL return 404.

#### Scenario: Get details

- **WHEN** a client fetches an existing conversation id
- **THEN** the API returns the conversation with its messages and escalation records

#### Scenario: Missing conversation

- **WHEN** a client fetches an unknown conversation id
- **THEN** the API returns 404

### Requirement: Conversation metrics

The system SHALL provide `GET /api/metrics` returning the percent of auto-answered messages (those not escalated), the average response time in seconds, and the count of escalations over the requested period.

#### Scenario: Metrics returned

- **WHEN** a client requests `GET /api/metrics`
- **THEN** the API returns auto-answer percent, average response time, and escalation count based on persisted conversations and messages
