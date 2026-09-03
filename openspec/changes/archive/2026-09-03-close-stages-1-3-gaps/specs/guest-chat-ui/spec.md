## ADDED Requirements

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
