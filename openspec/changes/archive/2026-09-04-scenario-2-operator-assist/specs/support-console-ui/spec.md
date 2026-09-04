## MODIFIED Requirements

### Requirement: Support console uses live document APIs and honest unavailable states

The knowledge-base section SHALL use the live documents endpoints that already exist in backend for list, upload, detail, reindex, and delete flows. The support chat and operator workspace SHALL use live conversation endpoints (`GET /api/conversations`, `GET /api/conversations/{id}`, operator reply, resolve). Console sections whose backend endpoint is not yet implemented SHALL display an explicit unavailable state instead of mock data. They SHALL NOT call `/api/operator/tickets`.

#### Scenario: Knowledge base loads live documents

- **WHEN** a support user opens `/knowledge-base` and backend documents API is available
- **THEN** the page loads its list from `/backend/api/documents`

#### Scenario: Support chat loads live conversations

- **WHEN** a support user opens `/chat/support` and backend publishes `/api/conversations`
- **THEN** the page renders the conversation list from that API instead of an unavailable placeholder

## ADDED Requirements

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
