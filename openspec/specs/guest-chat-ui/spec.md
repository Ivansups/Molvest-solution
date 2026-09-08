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

### Requirement: Guest chat shows operator replies

After the guest has a `conversation_id`, the guest chat SHALL refresh that conversation at least every 5 seconds and append messages with role `operator` (and any new `assistant` messages in auto mode) to the transcript. The guest UI SHALL NOT render `suggested_response`.

#### Scenario: Operator reply appears for the guest

- **WHEN** an operator has posted a reply to the guest's escalated conversation
- **THEN** the guest transcript shows that operator message without a full page reload

#### Scenario: Draft is hidden from the guest

- **WHEN** the conversation has a non-empty `suggested_response`
- **THEN** the guest chat does not display that draft text as a message

### Requirement: Guest chat visibly reports response processing
The guest chat SHALL show an in-transcript processing indicator while its chat
mutation is pending. The indicator SHALL distinguish an image analysis from a
text response generation and SHALL disappear after either success or failure.

#### Scenario: Text response is being generated
- **WHEN** a guest submits a text question and `POST /chat` is pending
- **THEN** the transcript shows that the agent is forming a response

#### Scenario: Screenshot is being analysed
- **WHEN** a guest submits a message with an attached image and `POST /chat` is pending
- **THEN** the transcript shows that the image is being analysed

### Requirement: Guest chat exposes source excerpts
The guest chat SHALL render each returned source as an interactive document
control and SHALL reveal its `chunk_text` when the guest activates that control.

#### Scenario: Guest opens a source citation
- **WHEN** an assistant message has a source and the guest activates its document title
- **THEN** the UI shows the readable source fragment for that source

### Requirement: Guest can start a new local conversation
The guest chat SHALL provide a visible "New conversation" control that removes
`guest_conversation_id` from `sessionStorage` and clears the local transcript.
The next guest message SHALL be sent without a `conversation_id`.

#### Scenario: Guest resets a current conversation
- **WHEN** the guest activates "New conversation"
- **THEN** the transcript is empty and no guest conversation identifier remains in session storage

#### Scenario: Previous request finishes after reset
- **WHEN** the guest resets a conversation while its request is still pending
- **THEN** the late response does not restore the previous identifier or messages

#### Scenario: Guest sends after reset
- **WHEN** the guest submits the first message after a reset
- **THEN** the chat request has `conversation_id` set to null and backend creates a new conversation

