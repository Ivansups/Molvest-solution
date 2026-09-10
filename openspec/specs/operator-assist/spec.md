## Purpose

Operator assist behind the support console: draft vs auto mode, on-demand GigaChat draft, operator reply and resolve. Guest follow-ups after escalation must not spend model tokens until the operator asks.

## Requirements

### Requirement: Assist mode is a single config value

The system SHALL read operator assist mode from one effective configuration value with allowed values `draft` or `auto`. The default SHALL be `draft` (from environment `OPERATOR_ASSIST_MODE` when no runtime override is set). The setting SHALL NOT be hardcoded in graph nodes or UI. Admins SHALL be able to change the effective value through `PUT /api/settings`; the guest dialog path SHALL honor the effective value on subsequent turns without an API restart.

#### Scenario: Default is draft

- **WHEN** the setting is unset and no runtime override exists
- **THEN** the system treats assist mode as `draft`

#### Scenario: Auto is honored

- **WHEN** effective assist mode is `auto` and an already escalated conversation receives a guest support question whose retrieval score is at or above the effective confidence threshold
- **THEN** the guest-facing `POST /chat` text is the generated answer, not only the escalation phrase

#### Scenario: Runtime override via settings API

- **WHEN** an admin sets `operator_assist_mode` to `auto` through `PUT /api/settings`
- **THEN** later escalated guest turns in that API process follow `auto` behavior without restarting the process

### Requirement: Escalation does not call generate

When a conversation first escalates because retrieval is below the confidence threshold on the guest `POST /chat` path (widget / support console), the system SHALL NOT call generate. It SHALL persist the guest escalation phrase, create the Escalation row, leave `suggested_response` empty, and return `escalated=true`. Bitrix and Redmine channel turns SHALL follow `bitrix-escalation-handoff` instead: they fill `suggested_response` after commit and SHALL NOT send the draft to the guest.

#### Scenario: First escalation has no draft

- **WHEN** a guest message on an `open` conversation scores below the threshold via `POST /chat`
- **THEN** the conversation becomes `escalated`, one Escalation row exists, `suggested_response` is empty, generate was not called, and the HTTP text is the guest escalation phrase

### Requirement: Escalated draft mode does not call the model

When conversation status is `escalated` and assist mode is `draft`, a later guest `POST /chat` SHALL persist the user message, keep status `escalated`, SHALL NOT call retrieve or generate, and SHALL NOT persist a new assistant message. The HTTP response SHALL have `escalated=true`. `suggested_response` SHALL stay as it was.

#### Scenario: Follow-up while waiting for operator

- **WHEN** a guest sends another support question on an already `escalated` conversation in `draft` mode
- **THEN** a new user message is stored, GigaChat generate is not called, `suggested_response` is unchanged, and the guest text is not a model draft

### Requirement: Operator can generate a draft on demand

The system SHALL provide `POST /api/conversations/{id}/suggest` authenticated with the internal service token. The body SHALL include `installation_id`. For an `escalated` conversation in that installation the system SHALL run retrieve and generate against the latest guest message and history, store the model text in `suggested_response`, and SHALL NOT append a user or assistant message or change status. This SHALL be the only on-demand console path that fills an operator draft; the live Bitrix thread assist in draft mode may also fill `suggested_response` automatically while processing a user message in the thread. The graph SHALL NOT open its own database session. A conversation that is not `escalated`, belongs to another installation, or has no guest message SHALL NOT generate a draft.

#### Scenario: Operator generates the draft

- **WHEN** an operator requests a suggestion on an escalated conversation that has a guest message
- **THEN** `suggested_response` is replaced with generated text, the message list is unchanged, and status stays `escalated`

#### Scenario: Suggest rejected unless escalated

- **WHEN** an operator requests a suggestion on an `open` or `resolved` conversation
- **THEN** the API returns 409 and `suggested_response` is unchanged

### Requirement: Operator can send a reply

The system SHALL provide `POST /api/conversations/{id}/messages` authenticated with the internal service token. The body SHALL include `installation_id` and `text`. For an `escalated` conversation in that installation the system SHALL persist a message with role `operator` and clear `suggested_response`. The graph SHALL NOT run. A conversation that is not `escalated`, or belongs to another installation, SHALL NOT accept the reply.

#### Scenario: Operator reply is stored

- **WHEN** an operator posts non-empty text to an escalated conversation in the same installation
- **THEN** a message with role `operator` exists, `suggested_response` is empty, and status stays `escalated`

#### Scenario: Reply rejected unless escalated

- **WHEN** an operator posts a reply to an `open` or `resolved` conversation
- **THEN** the API returns 409 and no operator message is stored

### Requirement: Operator can resolve a ticket

The system SHALL provide `POST /api/conversations/{id}/resolve` authenticated with the internal service token. The body SHALL include `installation_id`. The system SHALL change status only through the transition service `escalated → resolved`, set `resolved_at` on open escalations of that conversation, and clear `suggested_response`. Repeating the call on an already `resolved` conversation SHALL succeed without a second transition.

#### Scenario: Resolve closes the ticket

- **WHEN** an operator resolves an `escalated` conversation
- **THEN** status is `resolved`, escalations have `resolved_at` set, and `suggested_response` is empty

#### Scenario: Resolve is idempotent

- **WHEN** resolve is called twice on the same conversation
- **THEN** both calls succeed and status remains `resolved`

### Requirement: Operator workspace uses live escalations

The operator workspace at `/operator` and the support chat SHALL load escalated conversations from `GET /api/conversations?status=escalated`, show `suggested_response` from conversation details, offer a control to generate a draft via the suggest API, send replies through the operator messages API, and resolve through the resolve API. They SHALL NOT call `/api/operator/tickets`. Lists SHALL refresh at least every 5 seconds without an operator action. The generate control SHALL show a loading state until the suggest API returns and SHALL NOT send the draft to the guest by itself.

#### Scenario: Operator sees a new escalation

- **WHEN** a guest conversation becomes `escalated` while `/operator` is open
- **THEN** the ticket appears in the list without a full page reload and the assist panel is ready; the draft stays empty until the operator generates it

#### Scenario: Operator clicks generate

- **WHEN** the operator clicks generate on an escalated ticket
- **THEN** the frontend posts to the suggest API, the assist panel shows a loading state, and after success it shows the new `suggested_response` without adding a guest-visible message

#### Scenario: Operator sends the draft

- **WHEN** the operator clicks send on the suggested text
- **THEN** the frontend posts that text to the operator messages API and the transcript shows a message with role `operator`
