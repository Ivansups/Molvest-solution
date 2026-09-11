## ADDED Requirements

### Requirement: Forced handoff persists as an explicit escalation

When `POST /chat` carries `force_handoff=true`, the system SHALL persist the
turn as an escalation with the explicit handoff reason, SHALL NOT call
retrieve or generate, and SHALL return `escalated=true` with the guest
escalation phrase. Replaying the same forced handoff on an already
`escalated` conversation SHALL NOT create a second Escalation row.

#### Scenario: Button handoff creates one escalation

- **WHEN** a client calls `POST /chat` with `force_handoff=true` on an `open`
  conversation
- **THEN** status is `escalated`, one Escalation row has the handoff reason,
  generate was not called, and the response has `escalated=true`

#### Scenario: Forced handoff replay does not double-escalate

- **WHEN** `force_handoff=true` is sent twice against the same conversation
- **THEN** exactly one Escalation row exists and the status stays `escalated`

## MODIFIED Requirements

### Requirement: Conversation tables exist

The system SHALL persist Conversation, Message, and Escalation rows in
PostgreSQL with the fields defined in roadmap Stage 2, plus nullable
`Conversation.suggested_response`, nullable `Conversation.resolve_comment`,
and nullable `Conversation.resolve_confirmed_at`. Conversation.status SHALL
be one of `open`, `escalated`, `resolved`. Message.role SHALL be one of
`user`, `assistant`, `system`, `operator`. Timestamps SHALL be stored in UTC.
Alembic SHALL add `suggested_response` with a named column on
`conversations` and SHALL add named columns `resolve_comment` and
`resolve_confirmed_at`.

#### Scenario: Migration creates conversation tables

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Conversation, Message, and Escalation tables exist with the
  expected columns including `suggested_response`, `resolve_comment`, and
  `resolve_confirmed_at`

### Requirement: Chat persists user and assistant messages

The system SHALL persist every `POST /chat` turn: when `conversation_id` is
absent, SHALL create a `Conversation` with status `open`; SHALL write a
`Message` with role `user` (the incoming text). When the turn is a
guest-facing auto-answer, SHALL also write a `Message` with role `assistant`
carrying `content`, `confidence`, `sources`, and `escalated=false`. When the
turn is a first escalation in `draft` or `auto` on the widget path, SHALL
write a `Message` with role `system` carrying the guest escalation phrase
and SHALL NOT fill `suggested_response`. When the turn is a first
assist-mode `agent` hold of a generated answer, SHALL write the guest
escalation phrase (not the model text) as the guest-facing message, SHALL
fill `suggested_response` with the generated text, and SHALL NOT persist that
text as role `assistant`. When the turn is a guest follow-up on an already
`escalated` conversation in `draft` mode, SHALL NOT write an assistant or
extra system message and SHALL NOT change `suggested_response`. User and any
guest-facing message SHALL be committed in one transaction. Bitrix and
Redmine channel escalations MAY fill `suggested_response` after that commit
per `bitrix-escalation-handoff`.

#### Scenario: New conversation is created

- **WHEN** a client calls `POST /chat` without `conversation_id`
- **THEN** a `Conversation` row with status `open` and both user and
  assistant `Message` rows exist, and the response echoes the created
  `conversation_id`

#### Scenario: Existing conversation appends

- **WHEN** a client calls `POST /chat` with an existing `open`
  conversation_id and the graph does not escalate
- **THEN** the user and assistant messages are appended to that conversation
  and no new conversation row is created

#### Scenario: Draft follow-up does not add assistant text

- **WHEN** a client calls `POST /chat` on an already `escalated` conversation
  in `draft` mode
- **THEN** only the new user message is appended as a chat message and
  `suggested_response` is unchanged

#### Scenario: Assist mode agent stores draft not assistant answer

- **WHEN** a client calls `POST /chat` in assist mode `agent` and the graph
  produced a high-confidence answer
- **THEN** `suggested_response` holds that answer, no assistant message with
  that text exists, and the guest-facing stored text is the escalation phrase

### Requirement: Escalation is persisted and surfaced

The system SHALL, when the graph returns `escalated=true` on an `open`
conversation, change the conversation status `open → escalated` only via the
transition service and create one `Escalation` row with `conversation_id`,
`message_id`, `reason`, and `escalated_to`. The `reason` SHALL reflect the
source of escalation: a weak retrieval score, an explicit guest request to
hand off to a human, a forced `force_handoff`, or assist-mode `agent` hold of
a generated answer. The HTTP response SHALL carry `escalated=true` and the
guest-facing escalation phrase. On `POST /chat` in `draft` or `auto`,
`suggested_response` SHALL stay empty until an operator suggest call or a
channel fill. On `POST /chat` in `agent`, `suggested_response` SHALL
be filled by the delivery gate or `fill_escalation_draft`. On Bitrix and
Redmine channel turns, `suggested_response` SHALL be filled after commit per
`bitrix-escalation-handoff` unless already filled. Replaying the same
escalating turn (weak score, explicit handoff, or forced handoff) SHALL NOT
create a second `Escalation` row, and SHALL NOT downgrade an already
`escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the
  threshold via `POST /chat`
- **THEN** the conversation status becomes `escalated`, one `Escalation` row
  exists with a weak-score reason, `suggested_response` is empty, generate
  was not called, and the response has `escalated=true` with the guest
  escalation phrase

#### Scenario: Explicit handoff escalates with its own reason

- **WHEN** a client sends «позовите оператора»
- **THEN** the conversation status becomes `escalated`, one `Escalation` row
  exists with a handoff reason, generate was not called, and the response
  has `escalated=true` with the guest escalation phrase

#### Scenario: Replay does not double-escalate

- **WHEN** the same weak-scoring turn is sent twice against the same
  conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the
  status stays `escalated`

#### Scenario: Handoff replay does not double-escalate

- **WHEN** the same explicit handoff request is sent twice against the same
  conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the
  status stays `escalated`

### Requirement: Conversation details

The system SHALL provide `GET /api/conversations/{id}` returning the
conversation, `suggested_response` (nullable string), `resolve_comment`
(nullable string), `resolve_confirmed_at` (nullable UTC datetime), its
messages with `role` (including `operator`), `content`, `confidence`,
`escalated`, and `sources`, and escalations. An unknown id SHALL return 404.

#### Scenario: Get details

- **WHEN** a client fetches an existing conversation id
- **THEN** the API returns the conversation with its messages, escalation
  records, and `suggested_response`

#### Scenario: Missing conversation

- **WHEN** a client fetches an unknown conversation id
- **THEN** the API returns 404

#### Scenario: Details include resolve confirmation

- **WHEN** a client fetches a resolved conversation that was closed with a
  comment
- **THEN** the payload includes `resolve_comment` and `resolve_confirmed_at`
