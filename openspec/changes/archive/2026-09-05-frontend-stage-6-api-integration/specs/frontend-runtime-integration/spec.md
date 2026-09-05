## MODIFIED Requirements

### Requirement: Frontend services surface unsupported or unavailable APIs explicitly

The frontend SHALL surface a structured error and render explicit error UI when
a section depends on an unavailable API. Connected features SHALL use only
backend endpoint'ы published for stage 6 and SHALL NOT silently fall back to
mock data.

#### Scenario: Connected API is unavailable

- **WHEN** a connected page cannot load its published backend API
- **THEN** the page renders an unavailable state instead of fabricated data

#### Scenario: Backend is offline

- **WHEN** a connected page requests `/backend/health` while FastAPI is down
- **THEN** the page renders an explicit backend-unavailable state instead of
  fabricated data

#### Scenario: Unsupported legacy API is not requested

- **WHEN** dashboard, analytics, operator workspace or settings is opened
- **THEN** frontend does not request `/api/dashboard`, `/api/analytics`,
  `/api/operator/tickets` or `/api/settings`

## ADDED Requirements

### Requirement: Frontend uses bounded backend request timeouts

Frontend SHALL use a 10-second timeout for ordinary backend requests and a
60-second timeout for chat or AI draft generation.

#### Scenario: Ordinary request timeout

- **WHEN** a list, document or metrics request does not complete in 10 seconds
- **THEN** frontend treats the request as unavailable

#### Scenario: AI request timeout

- **WHEN** guest chat or operator draft generation takes longer than 10 seconds
- **THEN** frontend continues waiting until 60 seconds before timing out
