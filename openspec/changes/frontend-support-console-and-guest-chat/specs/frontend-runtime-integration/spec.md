## ADDED Requirements

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

When a console section depends on a backend endpoint that is missing,
unimplemented, or temporarily unavailable, the service layer SHALL raise a
structured error and the page SHALL render explicit unavailable or error UI.
The system SHALL NOT silently fall back to mock data for those sections.

#### Scenario: Service references an endpoint that backend does not publish

- **WHEN** the support chat service requests `/api/conversations`
- **THEN** the frontend surfaces a structured unsupported-endpoint error and the
  page shows an unavailable-state card

#### Scenario: Backend is offline

- **WHEN** a connected page requests `/backend/health` while FastAPI is down
- **THEN** the page renders an explicit backend-unavailable state instead of
  fabricated data

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
