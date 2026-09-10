## MODIFIED Requirements

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

The system SHALL, when the graph returns `escalated=true` on an `open` conversation, change the conversation status `open → escalated` only via the transition service and create one `Escalation` row with `conversation_id`, `message_id`, `reason`, and `escalated_to`. The HTTP response SHALL carry `escalated=true` and the guest-facing escalation phrase. On `POST /chat`, `suggested_response` SHALL stay empty until an operator suggest call. On Bitrix and Redmine channel turns, `suggested_response` SHALL be filled after commit per `bitrix-escalation-handoff`. Replaying the same weak-scoring turn SHALL NOT create a second `Escalation` row, and SHALL NOT downgrade an already `escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the threshold via `POST /chat`
- **THEN** the conversation status becomes `escalated`, one `Escalation` row exists, `suggested_response` is empty, generate was not called, and the response has `escalated=true` with the guest escalation phrase

#### Scenario: Replay does not double-escalate

- **WHEN** the same weak-scoring turn is sent twice against the same conversation
- **THEN** exactly one `Escalation` row exists for that conversation and the status stays `escalated`
