## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Guest and console share one knowledge-base workspace

The frontend SHALL use `NEXT_PUBLIC_WORKSPACE_ID` as the installation UUID for
guest chat, console conversations and knowledge-base document requests.

#### Scenario: Guest retrieves administrator documents

- **WHEN** an administrator uploads a document and a guest asks a related question
- **THEN** both requests use the same workspace UUID
