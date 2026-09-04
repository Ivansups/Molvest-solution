## ADDED Requirements

### Requirement: Guest chat shows operator replies

After the guest has a `conversation_id`, the guest chat SHALL refresh that conversation at least every 5 seconds and append messages with role `operator` (and any new `assistant` messages in auto mode) to the transcript. The guest UI SHALL NOT render `suggested_response`.

#### Scenario: Operator reply appears for the guest

- **WHEN** an operator has posted a reply to the guest's escalated conversation
- **THEN** the guest transcript shows that operator message without a full page reload

#### Scenario: Draft is hidden from the guest

- **WHEN** the conversation has a non-empty `suggested_response`
- **THEN** the guest chat does not display that draft text as a message
