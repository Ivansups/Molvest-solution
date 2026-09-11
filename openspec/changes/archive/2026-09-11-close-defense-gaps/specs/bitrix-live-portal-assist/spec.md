## ADDED Requirements

### Requirement: Assist mode `agent` after operator is draft-only

When a Bitrix bot or connector guest message arrives for a conversation that
is `escalated` or already has an operator message, and effective assist mode
is `agent`, the system SHALL behave as in `draft`: persist the user
message, run `generate_draft`, store `suggested_response`, and SHALL NOT send
a guest-facing auto-reply. Mode `auto` SHALL keep its existing auto-reply
path.

#### Scenario: Реплика гостя после эскалации в режиме `agent`

- **WHEN** an already `escalated` Bitrix bot dialog receives a new guest
  message in `agent` mode
- **THEN** a user message is stored, `suggested_response` is updated from
  generate_draft, and `imbot.message.add` is not called for a guest answer
