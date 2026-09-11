## Purpose

Authenticated support console shell, its role-aware navigation, and the protected routes rendered inside it.

## Requirements

### Requirement: Protected support routes require a support session

The system SHALL treat `/`, `/chat/support`, `/chat/support/:ticketId`,
`/knowledge-base`, `/settings`, `/analytics`, and `/operator` as support
console routes. A user without a support session SHALL be redirected to `/chat`.
The support login form at `/login` SHALL use empty inputs with placeholders
instead of prefilled credentials.

#### Scenario: Guest opens a protected route

- **WHEN** a user without a support session opens `/knowledge-base`
- **THEN** the system redirects the user to `/chat`

#### Scenario: Support login form is clean by default

- **WHEN** the login page is rendered
- **THEN** the email and password fields are empty and show placeholder hints
  instead of pre-entered values

### Requirement: Support routes share a persistent application shell

The system SHALL render all support console routes inside a shared shell with a
sidebar, top header, and consistent navigation. Navigating from the support
chat list to `/chat/support/:ticketId` SHALL preserve the shell instead of
switching to an isolated page layout.

#### Scenario: Open support chat detail

- **WHEN** a support user opens `/chat/support/123`
- **THEN** the page renders inside the same console shell with the sidebar and
  header still visible

### Requirement: Support console navigation is role-aware

The system SHALL show operator-only navigation and route access only for users
whose local session role is `operator`. Users with role `admin` SHALL NOT see
the operator-only navigation entry.

#### Scenario: Operator sees operator workspace

- **WHEN** a user with role `operator` opens the console
- **THEN** the navigation includes the operator workspace entry and `/operator`
  is accessible

#### Scenario: Admin does not see operator-only navigation

- **WHEN** a user with role `admin` opens the console
- **THEN** the navigation does not show the operator workspace entry

### Requirement: Support console uses live document APIs and honest unavailable states

The knowledge-base section SHALL use the live documents endpoints that already exist in backend for list, upload, detail, reindex, and delete flows. The support chat and operator workspace SHALL use live conversation endpoints (`GET /api/conversations`, `GET /api/conversations/{id}`, operator reply, resolve). The home dashboard and analytics section SHALL use live `GET /api/metrics`. The settings section SHALL use live `GET` / `PUT /api/settings` for confidence threshold and operator assist mode. Console sections whose backend endpoint is not yet implemented SHALL display an explicit unavailable state instead of mock data. They SHALL NOT call `/api/operator/tickets`, `/api/dashboard`, or `/api/analytics`.

#### Scenario: Knowledge base loads live documents

- **WHEN** a support user opens `/knowledge-base` and backend documents API is available
- **THEN** the page loads its list from `/backend/api/documents`

#### Scenario: Support chat loads live conversations

- **WHEN** a support user opens `/chat/support` and backend publishes `/api/conversations`
- **THEN** the page renders the conversation list from that API instead of an unavailable placeholder

#### Scenario: Dashboard and analytics use metrics API

- **WHEN** a support user opens `/` or `/analytics`
- **THEN** metrics are loaded from `/api/metrics` and not from `/api/dashboard` or `/api/analytics`

#### Scenario: Settings use settings API

- **WHEN** a support user opens `/settings` and the settings API is available
- **THEN** the page loads threshold and assist mode from `/api/settings`

### Requirement: Dashboard shows live conversation metrics

The home console route `/` SHALL display the three aggregates from `GET /api/metrics` for the signed-in user's installation: auto-answer percent, average response time in seconds, and escalation count. The page MAY keep existing health and document summary cards. It SHALL NOT call `/api/dashboard` or `/api/analytics` for these figures. The console SHALL treat the metrics API as the source of these numbers (no invented client-side aggregates). Embedding Grafana or other external observability UIs is out of scope for this requirement.

#### Scenario: Metrics cards render from API

- **WHEN** a support user opens `/` and `GET /api/metrics` succeeds
- **THEN** the dashboard shows auto-answer percent, average response time, and escalation count from that response

#### Scenario: Metrics failure is honest

- **WHEN** a support user opens `/` and `GET /api/metrics` fails
- **THEN** the dashboard shows an explicit unavailable or error state for metrics and does not invent numbers

### Requirement: Analytics page uses live metrics API

The `/analytics` route SHALL load data from `GET /api/metrics` (optionally with `date_from` / `date_to`). It SHALL NOT call `/api/analytics`. It SHALL NOT render mock charts or mock log tables as if they were live backend data.

#### Scenario: Analytics without dead endpoint

- **WHEN** a support user opens `/analytics` and metrics API is available
- **THEN** the page displays metrics derived from `GET /api/metrics` and does not request `/api/analytics`

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

### Requirement: Resolve from the console uses the confirmation modal

When an operator chooses to mark a conversation resolved from `/operator` or
`/chat/support`, the UI SHALL follow `resolve-confirmation`: show the
yes/no modal with optional comment, and POST resolve only after yes.

#### Scenario: Resolve menu opens the modal first

- **WHEN** an operator chooses to mark the conversation resolved
- **THEN** a confirmation modal is shown before any resolve API call
