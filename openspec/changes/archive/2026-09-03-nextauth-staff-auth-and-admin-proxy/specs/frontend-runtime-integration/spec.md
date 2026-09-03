## MODIFIED Requirements

### Requirement: Frontend proxies connected backend APIs through a stable local path

The system SHALL proxy guest browser requests through `/backend/:path*` to the
configured backend base URL. Frontend services for connected guest features
SHALL use the proxy path rather than a hard-coded backend host in the browser.
Admin document and other support-console requests SHALL go through Next.js
server route handlers or server actions instead of direct browser calls to
FastAPI admin routes.

#### Scenario: Health check goes through the frontend proxy

- **WHEN** the dashboard requests backend health
- **THEN** the frontend calls `/backend/health`, which is rewritten to the
  configured FastAPI base URL

#### Scenario: Guest chat goes through the frontend proxy

- **WHEN** the chat UI sends a request to backend chat
- **THEN** the frontend calls `/backend/chat` instead of calling the backend
  host directly from the browser

#### Scenario: Admin document calls stay on the Next.js server hop

- **WHEN** an authenticated staff user opens the knowledge-base or uploads a
  document
- **THEN** the browser calls a Next.js admin handler and FastAPI receives the
  downstream request from the Next.js server rather than directly from the
  browser
