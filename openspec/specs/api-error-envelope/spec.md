## Purpose

Return FastAPI failures as one JSON shape so clients can show a safe message and correlate logs by request id.

## Requirements

### Requirement: Failures use one JSON envelope

FastAPI SHALL return errors as JSON with fields `error`, `detail`, and `request_id`. `request_id` SHALL be the same value as the `x-request-id` response header. HTTP errors SHALL use `error` equal to `http_error`. Unhandled exceptions SHALL use `error` equal to `internal_error` and SHALL NOT leak a stack trace in `detail`.

#### Scenario: HTTP 404 uses the envelope

- **WHEN** a client fetches an unknown document id
- **THEN** the body is JSON with `error`, `detail`, and `request_id`, and `x-request-id` matches `request_id`

#### Scenario: Unhandled exception uses the envelope

- **WHEN** a domain route raises an unexpected exception
- **THEN** the API returns 500 with `error` equal to `internal_error`, a safe `detail`, and `request_id`
