## MODIFIED Requirements

### Requirement: Reindex is a no-op reset

`POST /api/documents/{id}/reindex` SHALL set the document status to `PENDING` and SHALL NOT create, replace, or delete chunks. Calling it twice SHALL leave the document `PENDING`. A missing id SHALL return 404.

#### Scenario: Reindex pending document

- **WHEN** a client calls reindex on an existing document
- **THEN** the API returns the document with status `PENDING`

#### Scenario: Reindex is idempotent

- **WHEN** a client calls reindex twice on the same document
- **THEN** both calls succeed and the document status is `PENDING`

### Requirement: Reindex rebuilds document chunks

`POST /api/documents/{id}/reindex` SHALL extract text, chunk, embed, and atomically replace the document's chunks, then set the document status to `INDEXED`. The API response SHALL include the rebuilt chunks. Calling reindex twice on the same document SHALL both succeed and leave it `INDEXED` with the new chunks. A missing or unreadable document SHALL return an error without leaving a partial state.

#### Scenario: Reindex an uploaded document

- **WHEN** a client calls reindex on an existing document with readable content
- **THEN** the API returns the document with status `INDEXED` and its rebuilt chunks

#### Scenario: Reindex is idempotent

- **WHEN** a client calls reindex twice on the same document
- **THEN** both calls succeed and the document status is `INDEXED`

#### Scenario: Reindex failure is surfaced

- **WHEN** extraction or embedding fails during reindex
- **THEN** the API returns an error and the document does not expose partial chunks
