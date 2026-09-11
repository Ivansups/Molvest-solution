## ADDED Requirements

### Requirement: Assist mode `agent` does not write the generated answer into the ticket

When effective assist mode is `agent`, a Redmine user turn SHALL NOT
send the generated answer to the requester even if the retrieval score is at
or above the threshold. The turn SHALL go through the same service-layer
delivery gate as the widget and Bitrix: conversation `escalated`,
`suggested_response` filled, no guest-facing ticket note/SMTP with the model
text.

#### Scenario: Высокий скор в режиме `agent` не отвечает в тикет

- **WHEN** assist mode is `agent` and a user ticket message scores at
  or above the threshold
- **THEN** the conversation is `escalated`, `suggested_response` holds the
  generated text, and no guest-facing ticket reply is sent

## MODIFIED Requirements

### Requirement: Ответ агента уходит в тот же тикет

When a Redmine user turn produces a guest-facing answer, the system SHALL
deliver it to that ticket after commit (Redmine note and/or SMTP, as
configured). A guest-facing answer happens when assist mode is not
`agent` and the turn is not an escalation. When the turn is an
operator message, an escalation, or an assist-mode `agent` hold, the system
SHALL NOT send that answer to the requester.

#### Scenario: Автоответ в тикет

- **WHEN** a user ticket message scores at or above the threshold and assist
  mode is `auto` or `draft` on an `open` conversation
- **THEN** the generated answer is persisted as assistant and, after commit,
  sent to that ticket

#### Scenario: Эскалация не пишет в тикет гостю

- **WHEN** a user ticket message scores below the threshold
- **THEN** the conversation is `escalated`, `suggested_response` is filled
  per `bitrix-escalation-handoff`, and no guest-facing ticket reply is sent
