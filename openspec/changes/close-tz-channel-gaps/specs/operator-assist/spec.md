## MODIFIED Requirements

### Requirement: Escalation does not call generate

When a conversation first escalates because retrieval is below the
confidence threshold on the guest `POST /chat` path (widget / support
console), the system SHALL NOT call generate. It SHALL persist the guest
escalation phrase, create the Escalation row, leave `suggested_response`
empty, and return `escalated=true`. Bitrix and Redmine channel turns
SHALL follow `bitrix-escalation-handoff` instead: they fill
`suggested_response` after commit and SHALL NOT send the draft to the
guest.

#### Scenario: First escalation has no draft

- **WHEN** a guest message on an `open` conversation scores below the threshold via `POST /chat`
- **THEN** the conversation becomes `escalated`, one Escalation row exists, `suggested_response` is empty, generate was not called, and the HTTP text is the guest escalation phrase
