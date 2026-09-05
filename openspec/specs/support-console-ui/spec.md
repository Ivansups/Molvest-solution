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

The knowledge-base section SHALL use the live documents endpoints for list,
upload, detail, reindex and delete flows. The support chat and operator
workspace SHALL use `GET /api/conversations`,
`GET /api/conversations/{id}`, operator reply, resolve and suggest endpoints.
Dashboard and analytics SHALL use `GET /api/metrics` and conversation lists.
Settings SHALL render an explicit stage 1-6 unavailable state and SHALL NOT
request a backend settings API. The console SHALL NOT call
`/api/operator/tickets`.

#### Scenario: Knowledge base loads live documents

- **WHEN** a support user opens `/knowledge-base` and backend documents API is available
- **THEN** the page loads its list from `/backend/api/documents`

#### Scenario: Support chat loads live conversations

- **WHEN** a support user opens `/chat/support`
- **THEN** the page renders the conversation list from `GET /api/conversations`

#### Scenario: Dashboard loads stage 6 metrics

- **WHEN** a support user opens the dashboard or analytics
- **THEN** the page displays data from `GET /api/metrics`

#### Scenario: Settings is outside implemented stages

- **WHEN** a support user opens `/settings`
- **THEN** the page shows an unavailable state without a backend request

### Requirement: Support compose sends operator replies not guest chat

When the support user submits text from `/chat/support` or `/operator`, the frontend SHALL POST to `/api/conversations/{id}/messages` and SHALL NOT send that text to `POST /chat`. Resolve from the support UI SHALL POST to `/api/conversations/{id}/resolve`. The assist panel SHALL include a generate-draft action that POSTs to `/api/conversations/{id}/suggest` and SHALL NOT call `POST /chat` for that action.

#### Scenario: Support send does not hit guest chat

- **WHEN** an operator submits a reply in support chat
- **THEN** the request goes to the operator messages API and `POST /chat` is not called

#### Scenario: Generate draft from the panel

- **WHEN** an operator clicks generate in the assist panel
- **THEN** the frontend calls the suggest API and does not call `POST /chat`

#### Scenario: Resolve from the menu

- **WHEN** an operator chooses to mark the conversation resolved
- **THEN** the frontend calls the resolve API and the conversation status shown becomes `resolved`

### Requirement: Guest and console share one knowledge-base workspace

The frontend SHALL use `NEXT_PUBLIC_WORKSPACE_ID` as the installation UUID for
guest chat, console conversations and knowledge-base document requests.

#### Scenario: Guest retrieves administrator documents

- **WHEN** an administrator uploads a document and a guest asks a related question
- **THEN** both requests use the same workspace UUID
