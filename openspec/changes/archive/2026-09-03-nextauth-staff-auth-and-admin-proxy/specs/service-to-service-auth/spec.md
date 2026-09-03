## MODIFIED Requirements

### Requirement: Admin routes require the internal service token when configured

When `INTERNAL_SERVICE_TOKEN` is a non-empty string, FastAPI SHALL accept admin
requests only if the header `X-Internal-Token` matches that value exactly.
`/health`, `/docs`, `/openapi.json`, `/redoc`, and the public guest chat route
SHALL remain reachable without the header. When the setting is empty, FastAPI
SHALL not reject admin requests for a missing token.

#### Scenario: Valid token is accepted for admin API

- **WHEN** a client calls `/api/documents` with `X-Internal-Token` equal to the
  configured token
- **THEN** the request is processed and is not rejected with 401

#### Scenario: Missing or wrong token is rejected on admin API

- **WHEN** the token is configured and a client calls `/api/documents` without
  the header or with a different value
- **THEN** the API returns 401 and does not mutate or expose admin data

#### Scenario: Guest chat stays public

- **WHEN** a guest calls `POST /chat` without the token header
- **THEN** the API does not reject the request for missing `X-Internal-Token`

### Requirement: Next.js attaches the token only on the admin server hop

The Next.js server SHALL add `X-Internal-Token` when it forwards authenticated
support-console admin requests to FastAPI. The browser and any client bundle
SHALL NOT receive the token value, and guest traffic SHALL NOT depend on it.

#### Scenario: Admin documents request includes the token

- **WHEN** an authenticated staff user requests the documents admin API through
  the Next.js server
- **THEN** FastAPI receives `X-Internal-Token` from the Next.js hop and accepts
  the admin request
