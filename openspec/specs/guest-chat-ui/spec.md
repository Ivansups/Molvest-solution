## Purpose

Public chat workspace at `/chat` for 1C users without a support account, backed by live `POST /chat` responses.

## Requirements

### Requirement: Guest chat is accessible without authentication

The system SHALL expose `/chat` as a public route for 1C users without a
support account. The guest route SHALL render independently of any support
session and SHALL provide a visible path to the support login page at `/login`.

#### Scenario: Open guest chat as an unauthenticated user

- **WHEN** a user without a support session opens `/chat`
- **THEN** the system renders the guest chat workspace and a visible action to
  open `/login`

### Requirement: Guest chat submits live requests to backend chat

The system SHALL send guest messages through the frontend proxy to
`POST /chat`. Each request SHALL include a generated `message_id`, a guest
`user_id`, the current `conversation_id` when present, the text payload when
provided, and `image_base64` when the user attaches a screenshot.

#### Scenario: Send a text-only guest message

- **WHEN** a guest submits a text question from `/chat`
- **THEN** the frontend sends the request to `/backend/chat` and preserves the
  returned `conversation_id` for the next message

#### Scenario: Send a guest message with a screenshot

- **WHEN** a guest attaches a PNG or JPEG screenshot and submits the message
- **THEN** the frontend sends the screenshot as `image_base64` to
  `/backend/chat` and shows the selected image preview in the UI

### Requirement: Guest chat renders live backend responses without fallback mocks

The system SHALL render the response returned by backend `/chat`, including
`text`, `confidence`, `escalated`, and `sources`. If the request fails, the
frontend SHALL show error feedback and SHALL NOT generate a mock assistant
answer or placeholder response.

#### Scenario: Backend returns an answer

- **WHEN** backend `/chat` responds successfully
- **THEN** the guest chat displays the returned answer content, confidence badge
  when present, escalation state, and any returned source titles

#### Scenario: Backend request fails

- **WHEN** backend `/chat` is unavailable or returns an error
- **THEN** the frontend shows an error notification and no synthetic assistant
  reply is appended to the conversation

### Requirement: Guest chat uses the admin installation workspace

Guest `POST /chat` requests SHALL send a `workspace_id` that the backend resolves to the same `installation_id` used by the admin knowledge-base upload. If `workspace_id` is a UUID, the backend SHALL use that UUID as `installation_id` without hashing.

#### Scenario: Guest question sees admin documents

- **WHEN** an admin has indexed a document for the default installation and a guest asks a related question
- **THEN** retrieval can return chunks from that document

### Requirement: Guest screenshots are compressed before send

The guest chat SHALL resize an attached screenshot so the long side is at most 1024 pixels, then send the stripped base64 in `image_base64`. The chat request timeout SHALL be long enough for a Vision call (at least 60 seconds).

#### Scenario: Large screenshot is resized

- **WHEN** a guest attaches a screenshot larger than 1024 pixels on the long side
- **THEN** the payload sent as `image_base64` is from a resized image

#### Scenario: Vision request is not cut at 10 seconds

- **WHEN** a guest sends a message with an image
- **THEN** the frontend waits at least 60 seconds before treating the request as timed out

