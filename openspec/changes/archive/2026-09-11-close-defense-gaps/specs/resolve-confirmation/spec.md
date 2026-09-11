## ADDED Requirements

### Requirement: Operator confirms resolution before status changes

The system SHALL change `Conversation.status` to `resolved` only after an
operator confirmation on `POST /api/conversations/{id}/resolve`. The request
body SHALL include `installation_id` and `confirmed` set to `true`. An
optional `comment` string MAY be sent. The status transition SHALL still go
only through `transition_status` (`escalated → resolved`). Guest CSAT in
Bitrix or Redmine is out of contract for this requirement.

#### Scenario: Confirmed resolve closes the ticket

- **WHEN** an operator posts resolve with `confirmed=true` on an `escalated`
  conversation
- **THEN** status becomes `resolved`, open escalations get `resolved_at`, and
  `suggested_response` is empty

#### Scenario: Missing or false confirmation is rejected

- **WHEN** an operator posts resolve without `confirmed=true`
- **THEN** the API returns 422 and the conversation stays `escalated`

#### Scenario: Resolve stays idempotent when already resolved

- **WHEN** resolve with `confirmed=true` is called on an already `resolved`
  conversation
- **THEN** both the first and second calls succeed and status remains
  `resolved`

### Requirement: Resolution confirmation is stored

The system SHALL persist that the operator confirmed close: `resolve_confirmed_at`
(UTC timestamptz) and optional `resolve_comment` on the conversation. The
comment SHALL NOT be sent to the guest and SHALL NOT be posted to Bitrix or
Redmine. `GET /api/conversations/{id}` SHALL return these fields.

#### Scenario: Comment is stored with confirmation

- **WHEN** an operator resolves with `confirmed=true` and comment «готово»
- **THEN** conversation details include that comment and a non-null
  `resolve_confirmed_at`

#### Scenario: Resolve without comment is allowed

- **WHEN** an operator resolves with `confirmed=true` and no comment
- **THEN** status is `resolved` and `resolve_comment` is null

### Requirement: Console asks before calling resolve

The operator workspace (`/operator`) and support chat (`/chat/support`) SHALL
show a modal asking whether the issue is resolved (yes/no) and offering an
optional comment field. Yes SHALL POST resolve with `confirmed=true`. No SHALL
NOT call the resolve API and SHALL leave the conversation `escalated`.

#### Scenario: Operator answers yes in the modal

- **WHEN** the operator chooses yes and submits the modal
- **THEN** the frontend posts to the resolve API with `confirmed=true` and the
  shown status becomes `resolved`

#### Scenario: Operator answers no in the modal

- **WHEN** the operator chooses no
- **THEN** no resolve request is sent and the conversation remains `escalated`
