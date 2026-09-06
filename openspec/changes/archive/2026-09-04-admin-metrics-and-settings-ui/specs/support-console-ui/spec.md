## ADDED Requirements

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

The `/settings` route SHALL load and save `confidence_threshold` and `operator_assist_mode` via `GET` / `PUT /api/settings`. The form SHALL NOT require Bitrix, Redmine, or model fields. While the settings API is unavailable, the page SHALL show an explicit unavailable state rather than mock configuration.

#### Scenario: Save settings through live API

- **WHEN** a support admin changes the confidence threshold and assist mode and submits the form
- **THEN** the frontend sends `PUT /api/settings` with those two fields and on success reflects the saved values

#### Scenario: Settings unavailable without mocks

- **WHEN** `GET /api/settings` fails
- **THEN** the settings page shows an unavailable state and does not fill the form from mock data

## MODIFIED Requirements

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
