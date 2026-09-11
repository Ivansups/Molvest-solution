## ADDED Requirements

### Requirement: Settings labels describe the three assist modes in plain language

The `/settings` form SHALL present `operator_assist_mode` as three options
whose visible labels match the delivery policy: auto-answer when confident
(`auto`); auto-answer until escalation, then drafts (`draft`); never send
the raw model answer until the operator sends (settings value `agent`).
Labels SHALL NOT claim that `draft` only generates on an operator button
press, and SHALL NOT claim that `auto` only applies after escalation.

#### Scenario: Admin sees agent in the select

- **WHEN** a support user opens `/settings`
- **THEN** the assist-mode control offers `draft`, `auto`, and `agent`
  with labels that distinguish first-reply auto-answer from assist mode
  `agent`

### Requirement: Resolve from the console uses the confirmation modal

When an operator chooses to mark a conversation resolved from `/operator` or
`/chat/support`, the UI SHALL follow `resolve-confirmation`: show the
yes/no modal with optional comment, and POST resolve only after yes.

#### Scenario: Resolve menu opens the modal first

- **WHEN** an operator chooses to mark the conversation resolved
- **THEN** a confirmation modal is shown before any resolve API call

## MODIFIED Requirements

### Requirement: Settings page edits threshold and assist mode live

The `/settings` route SHALL load and save `confidence_threshold` and
`operator_assist_mode` via `GET` / `PUT /api/settings`. The assist mode field
SHALL accept `draft`, `auto`, and `agent`. The form SHALL NOT require
Bitrix, Redmine, or model fields. While the settings API is unavailable, the
page SHALL show an explicit unavailable state rather than mock configuration.

#### Scenario: Save settings through live API

- **WHEN** a support admin changes the confidence threshold and assist mode
  and submits the form
- **THEN** the frontend sends `PUT /api/settings` with those two fields and
  on success reflects the saved values

#### Scenario: Settings unavailable without mocks

- **WHEN** `GET /api/settings` fails
- **THEN** the settings page shows an unavailable state and does not fill
  the form from mock data

#### Scenario: Save agent through live API

- **WHEN** a support admin selects `agent` and submits the form
- **THEN** the frontend sends `operator_assist_mode` `"agent"` and on
  success the select shows that value

### Requirement: Support compose sends operator replies not guest chat

When the support user submits text from `/chat/support` or `/operator`, the
frontend SHALL POST to `/api/conversations/{id}/messages` and SHALL NOT send
that text to `POST /chat`. Resolve from the support UI SHALL POST to
`/api/conversations/{id}/resolve` with `confirmed=true` after the
confirmation modal. The assist panel SHALL include a generate-draft action
that POSTs to `/api/conversations/{id}/suggest` and SHALL NOT call
`POST /chat` for that action.

#### Scenario: Support send does not hit guest chat

- **WHEN** an operator submits a reply in support chat
- **THEN** the request goes to the operator messages API and `POST /chat` is
  not called

#### Scenario: Generate draft from the panel

- **WHEN** an operator clicks generate in the assist panel
- **THEN** the frontend calls the suggest API and does not call `POST /chat`

#### Scenario: Resolve from the menu

- **WHEN** an operator chooses to mark the conversation resolved and confirms
  yes in the modal
- **THEN** the frontend calls the resolve API with `confirmed=true` and the
  conversation status shown becomes `resolved`
