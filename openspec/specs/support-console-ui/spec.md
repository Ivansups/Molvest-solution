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

The knowledge-base section SHALL use the live documents endpoints that already
exist in backend for list, upload, detail, reindex, and delete flows. Console
sections whose backend endpoint is not yet implemented SHALL display an explicit
unavailable state instead of mock data.

#### Scenario: Knowledge base loads live documents

- **WHEN** a support user opens `/knowledge-base` and backend documents API is available
- **THEN** the page loads its list from `/backend/api/documents`

#### Scenario: Missing support chat API is surfaced honestly

- **WHEN** a support user opens `/chat/support` and backend does not publish
  `/api/conversations`
- **THEN** the page renders an explicit unavailable state describing the missing
  endpoint instead of a fake chat list
