## MODIFIED Requirements

### Requirement: Operator can generate a draft on demand

The system SHALL provide `POST /api/conversations/{id}/suggest` authenticated with the internal service token. The body SHALL include `installation_id`. For an `escalated` conversation in that installation the system SHALL run retrieve and generate against the latest guest message and history, store the model text in `suggested_response`, and SHALL NOT append a user or assistant message or change status. This SHALL be the only on-demand console path that fills an operator draft; the live Bitrix thread assist in draft mode may also fill `suggested_response` automatically while processing a user message in the thread. The graph SHALL NOT open its own database session. A conversation that is not `escalated`, belongs to another installation, or has no guest message SHALL NOT generate a draft.

#### Scenario: Operator generates the draft

- **WHEN** an operator requests a suggestion on an escalated conversation that has a guest message
- **THEN** `suggested_response` is replaced with generated text, the message list is unchanged, and status stays `escalated`

#### Scenario: Suggest rejected unless escalated

- **WHEN** an operator requests a suggestion on an `open` or `resolved` conversation
- **THEN** the API returns 409 and `suggested_response` is unchanged