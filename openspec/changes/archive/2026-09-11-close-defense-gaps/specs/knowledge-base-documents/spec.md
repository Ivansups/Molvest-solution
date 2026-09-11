## ADDED Requirements

### Requirement: Patch updates title and metadata without reindex

The system SHALL provide `PATCH /api/documents/{id}` authenticated with the
internal service token. The query SHALL require `installation_id`. The JSON
body SHALL accept optional `title` (non-empty string) and optional `metadata`
(JSON object). At least one of those fields SHALL be present; otherwise the
API returns 422. On success the system SHALL update only title and/or
`extra_metadata`, leave file bytes, chunks, `status`, and `kb_version`
unchanged, and SHALL NOT start indexing. A missing id or a document of
another installation SHALL return 404. The knowledge-base document form
SHALL call this PATCH instead of an unsupported-endpoint stub.

#### Scenario: Title change does not reindex

- **WHEN** a client PATCHes an indexed document with a new title
- **THEN** the stored title changes, chunk rows are unchanged, status stays
  `INDEXED`, and no reindex task is started

#### Scenario: Metadata change stores category and description

- **WHEN** a client PATCHes `metadata` with `category` and `description`
- **THEN** later `GET /api/documents/{id}` returns those keys in `metadata`

#### Scenario: Empty patch is rejected

- **WHEN** a client PATCHes a document with neither title nor metadata
- **THEN** the API returns 422 and the document is unchanged

#### Scenario: Console form uses PATCH

- **WHEN** a support user saves title, category, and description on the
  document card
- **THEN** the frontend sends PATCH to `/api/documents/{id}` and does not
  call an unsupported-endpoint helper

## MODIFIED Requirements

### Requirement: Per-document endpoints are scoped to one installation

`GET`, `PATCH`, `DELETE` and `POST .../reindex` on `/api/documents/{id}`
SHALL require an `installation_id` query parameter. A document that belongs
to another installation SHALL be indistinguishable from a missing one and
return 404. The support console SHALL send the installation id of the
signed-in staff session.

#### Scenario: Document of another installation

- **WHEN** a client fetches, patches, reindexes or deletes a document id with
  an `installation_id` that does not own it
- **THEN** the API returns 404 and the document is left untouched

#### Scenario: Request without an installation id

- **WHEN** a client calls a per-document endpoint without `installation_id`
- **THEN** the API rejects the request instead of resolving the document
