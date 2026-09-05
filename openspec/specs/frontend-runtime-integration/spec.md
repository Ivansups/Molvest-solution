## Purpose

Connects the Next.js frontend to FastAPI through a stable proxy path and keeps unavailable backend endpoints visible instead of masked by mock data.
## Requirements
### Requirement: Frontend proxies connected backend APIs through a stable local path

The system SHALL proxy connected browser requests through `/backend/:path*` to
the configured backend base URL. Frontend services for connected features SHALL
use the proxy path rather than a hard-coded backend host in the browser.

#### Scenario: Health check goes through the frontend proxy

- **WHEN** the dashboard requests backend health
- **THEN** the frontend calls `/backend/health`, which is rewritten to the
  configured FastAPI base URL

#### Scenario: Guest chat goes through the frontend proxy

- **WHEN** the chat UI sends a request to backend chat
- **THEN** the frontend calls `/backend/chat` instead of calling the backend
  host directly from the browser

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

### Requirement: Frontend runtime is SSR-safe and closed-contour-safe

The frontend SHALL avoid browser-only global access during server render, SHALL
use a local font stack that does not require fetching Google Fonts, and SHALL
provide a production build path compatible with the installed Next.js version.

#### Scenario: Server render does not touch browser globals

- **WHEN** the application server-renders a route such as `/login` or `/chat`
- **THEN** rendering succeeds without a `document is not defined` runtime error

#### Scenario: Production build works in a locked-down environment

- **WHEN** an operator runs `pnpm --dir frontend build`
- **THEN** the build completes without requiring external Google Fonts access

### Requirement: Frontend uses bounded backend request timeouts

Frontend SHALL use a 10-second timeout for ordinary backend requests and a
60-second timeout for chat or AI draft generation.

#### Scenario: Ordinary request timeout

- **WHEN** a list, document or metrics request does not complete in 10 seconds
- **THEN** frontend treats the request as unavailable

#### Scenario: AI request timeout

- **WHEN** guest chat or operator draft generation takes longer than 10 seconds
- **THEN** frontend continues waiting until 60 seconds before timing out
