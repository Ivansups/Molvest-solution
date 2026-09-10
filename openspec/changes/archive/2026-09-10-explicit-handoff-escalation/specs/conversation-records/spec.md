## MODIFIED Requirements

### Requirement: Escalation is persisted and surfaced

The system SHALL, when the graph returns `escalated=true` on an `open` conversation, change the conversation status `open → escalated` only via the transition service and create one `Escalation` row with `conversation_id`, `message_id`, `reason`, and `escalated_to`. The `reason` SHALL reflect the source of escalation: a weak retrieval score or an explicit guest request to hand off to a human. The HTTP response SHALL carry `escalated=true` and the guest-facing escalation phrase. `suggested_response` SHALL stay empty until an operator suggest call. Replaying the same escalating turn (weak score or explicit handoff) SHALL NOT create a second `Escalation` row, and SHALL NOT downgrade an already `escalated` conversation.

#### Scenario: Weak score escalates and persists

- **WHEN** a client sends a message whose best retrieval score is below the threshold
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