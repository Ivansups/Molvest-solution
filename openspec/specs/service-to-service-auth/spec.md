## Purpose

Protect FastAPI domain routes with a shared service token that Next.js attaches on the server hop. The browser never sees the token.

## Requirements

### Requirement: Domain routes require the internal service token when configured

When `INTERNAL_SERVICE_TOKEN` is a non-empty string, FastAPI SHALL accept domain requests only if the header `X-Internal-Token` matches that value exactly. `/health`, `/docs`, `/openapi.json`, and `/redoc` SHALL remain reachable without the header. When the setting is empty, FastAPI SHALL not reject requests for a missing token.

#### Scenario: Valid token is accepted

- **WHEN** a client calls `POST /chat` with `X-Internal-Token` equal to the configured token
- **THEN** the request is processed and is not rejected with 401

#### Scenario: Missing or wrong token is rejected

- **WHEN** the token is configured and a client calls `POST /chat` or `/api/documents` without the header or with a different value
- **THEN** the API returns 401 and does not run the agent or mutate documents

#### Scenario: Health stays public

- **WHEN** a client calls `GET /health` with no token header
- **THEN** the API returns 200

#### Scenario: Empty token disables the check

- **WHEN** `INTERNAL_SERVICE_TOKEN` is empty and a client calls `POST /chat` without the header
- **THEN** the API does not return 401 for that reason

### Requirement: Next.js attaches the token on the server hop

The Next.js server SHALL add `X-Internal-Token` when it forwards browser calls to FastAPI through the `/backend` proxy (or a later tRPC procedure that calls FastAPI). The browser and any tRPC client bundle SHALL NOT receive the token value.

#### Scenario: Proxied chat includes the token

- **WHEN** the guest chat sends a message through `/backend/chat` and the token is configured
- **THEN** FastAPI receives `X-Internal-Token` from the Next.js hop and accepts the request
