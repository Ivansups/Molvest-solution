## ADDED Requirements

### Requirement: Assist mode `agent` holds every generated answer for the operator

When effective assist mode is `agent` (the settings value: every AI reply
is a draft until the operator clicks Send, not the LangGraph agent), the
system SHALL NOT send the model's generated answer to the guest on any
channel. After the graph produces an answer, a service-layer delivery gate
SHALL: transition `open → escalated` through the status service, persist one
Escalation row with an assist-mode `agent` reason, store the generated text
in `suggested_response`, and return `escalated=true` with the guest
escalation phrase on the widget path. Routers and channel adapters SHALL
NOT implement this gate themselves. The LangGraph agent SHALL stay
channel-agnostic. The operator SHALL send the text to the guest only
through the existing operator Send API.

#### Scenario: High-confidence first reply is a draft

- **WHEN** assist mode is `agent` and a guest support question on an
  `open` conversation retrieves a best chunk score at or above the threshold
- **THEN** generate ran, `suggested_response` holds the generated text, status
  is `escalated`, no assistant message with that text is persisted, and the
  guest-facing chat text is the escalation phrase

#### Scenario: Widget, Bitrix and Redmine share the gate

- **WHEN** the same high-confidence question is processed in assist mode
  `agent` via `POST /chat`, a Bitrix bot turn, and a Redmine ticket turn
- **THEN** each path leaves `suggested_response` filled, does not deliver the
  generated answer to the requester, and does not branch the mode in a router

### Requirement: Assist mode `agent` follow-up refreshes the operator draft

When assist mode is `agent` and the conversation is already `escalated`
(or already has an operator message on a channel), a later guest message
SHALL persist the user text, update `suggested_response` via `generate_draft`,
SHALL NOT send a guest-facing auto-answer, and SHALL NOT change status away
from `escalated`.

#### Scenario: Second question still stays with the operator

- **WHEN** a guest sends another support question on an `escalated`
  conversation in assist mode `agent`
- **THEN** a new user message is stored, `suggested_response` is replaced
  with a new draft, and the guest does not receive the model text

## MODIFIED Requirements

### Requirement: Assist mode is a single config value

The system SHALL read operator assist mode from one effective configuration
value with allowed values `draft`, `auto`, or `agent`. The default
SHALL be `draft` (from environment `OPERATOR_ASSIST_MODE` when no runtime
override is set). The setting SHALL NOT be hardcoded in graph nodes or UI.
Admins SHALL be able to change the effective value through `PUT /api/settings`;
the guest dialog path SHALL honor the effective value on subsequent turns
without an API restart. The system SHALL NOT introduce a separate
`require_operator_confirm` flag. Allowed value `agent` is the settings
identifier for hold-every-reply until operator Send; it is not the
LangGraph agent. Existing stored or env values `draft` and
`auto` SHALL keep their previous meaning: `auto` may auto-answer the guest
when confidence is at or above the threshold even after escalation; `draft`
auto-answers only while the conversation is `open` and holds after
escalation.

#### Scenario: Default is draft

- **WHEN** the setting is unset and no runtime override exists
- **THEN** the system treats assist mode as `draft`

#### Scenario: Auto is honored

- **WHEN** effective assist mode is `auto` and an already escalated
  conversation receives a guest support question whose retrieval score is at
  or above the effective confidence threshold
- **THEN** the guest-facing `POST /chat` text is the generated answer, not
  only the escalation phrase

#### Scenario: Runtime override via settings API

- **WHEN** an admin sets `operator_assist_mode` to `auto` through
  `PUT /api/settings`
- **THEN** later escalated guest turns in that API process follow `auto`
  behavior without restarting the process

#### Scenario: Assist mode agent override via settings API

- **WHEN** an admin sets `operator_assist_mode` to `agent` through
  `PUT /api/settings`
- **THEN** later guest turns in that API process follow assist mode `agent`
  behavior without restarting the process

### Requirement: Escalation does not call generate

When a conversation first escalates because retrieval is below the confidence
threshold on the guest `POST /chat` path (widget / support console) and
assist mode is `draft` or `auto`, the system SHALL NOT call generate. It
SHALL persist the guest escalation phrase, create the Escalation row, leave
`suggested_response` empty, and return `escalated=true`. Bitrix and Redmine
channel turns SHALL follow `bitrix-escalation-handoff` instead: they fill
`suggested_response` after commit and SHALL NOT send the draft to the guest.
When assist mode is `agent`, a below-threshold first escalation SHALL
still skip generate inside the graph, then fill `suggested_response` after
commit through the existing `fill_escalation_draft` helper (including the
widget path). If `suggested_response` is already filled, that helper SHALL
NOT call generate again.

#### Scenario: First escalation has no draft

- **WHEN** a guest message on an `open` conversation scores below the
  threshold via `POST /chat` in `draft` mode
- **THEN** the conversation becomes `escalated`, one Escalation row exists,
  `suggested_response` is empty, generate was not called, and the HTTP text
  is the guest escalation phrase

#### Scenario: Assist mode agent weak score still gets a draft

- **WHEN** a guest message on an `open` conversation scores below the
  threshold via `POST /chat` in `agent` mode
- **THEN** the conversation becomes `escalated` and `suggested_response` is
  filled after commit unless generate_draft fails

### Requirement: Operator can resolve a ticket

The system SHALL provide `POST /api/conversations/{id}/resolve`
authenticated with the internal service token. The body SHALL include
`installation_id` and `confirmed=true` as required by `resolve-confirmation`.
The system SHALL change status only through the transition service
`escalated → resolved`, set `resolved_at` on open escalations of that
conversation, store the confirmation timestamp and optional comment, and
clear `suggested_response`. Repeating the call on an already `resolved`
conversation SHALL succeed without a second transition.

#### Scenario: Resolve closes the ticket

- **WHEN** an operator resolves an `escalated` conversation with
  `confirmed=true`
- **THEN** status is `resolved`, escalations have `resolved_at` set, and
  `suggested_response` is empty

#### Scenario: Resolve is idempotent

- **WHEN** resolve is called twice on the same conversation
- **THEN** both calls succeed and status remains `resolved`
