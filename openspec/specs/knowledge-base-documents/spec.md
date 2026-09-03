## Purpose

Storage and admin API for knowledge-base documents and chunks. A successful upload queues the same background indexing as reindex.

## Requirements

### Requirement: Document and chunk tables exist

The system SHALL persist Document and Chunk rows in PostgreSQL with the fields defined in roadmap Stage 2. Chunk.embedding SHALL be a nullable `vector(1024)` column (GigaChat `Embeddings`). The first Alembic revision SHALL enable the `vector` extension and create both tables. Indexes and constraints SHALL use names of the form `ix_<table>_<column>` and `uq_<table>_<column>`.

#### Scenario: Migration applies cleanly

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Document and Chunk tables exist and the `vector` extension is enabled

### Requirement: Upload creates a pending document

The system SHALL accept `POST /api/documents` as multipart form data with `file`, `title`, and `installation_id`. Optional `metadata` MAY be a JSON object string. Allowed file types are PDF, DOCX, HTML, and MD. On success the system SHALL store the file on disk, persist a Document with status `PENDING`, return `201` without waiting for embeddings, and SHALL start the same background indexing task used by reindex.

#### Scenario: Upload PDF

- **WHEN** a client uploads a PDF with a title and installation id
- **THEN** the API returns the document with status `PENDING` and the file is stored on disk

#### Scenario: Upload DOCX

- **WHEN** a client uploads a DOCX with a title and installation id
- **THEN** the API returns the document with status `PENDING` and the file is stored on disk

#### Scenario: Upload starts background indexing

- **WHEN** a client uploads a supported document
- **THEN** the API returns `201` with status `PENDING` and indexing of that document is started in the background

#### Scenario: Reject unsupported type

- **WHEN** a client uploads a file whose type is not PDF, DOCX, HTML, or MD
- **THEN** the API returns 422 and no document row is created

### Requirement: Duplicate file name is rejected

The system SHALL enforce uniqueness of `(installation_id, file_name)`. A second upload with the same pair SHALL fail with HTTP 409 and SHALL NOT replace the existing document.

#### Scenario: Same name in the same installation

- **WHEN** a client uploads a file whose `file_name` already exists for that `installation_id`
- **THEN** the API returns 409 and the original document is unchanged

#### Scenario: Same name in another installation

- **WHEN** a client uploads a file whose `file_name` exists only under a different `installation_id`
- **THEN** the API creates a new document

### Requirement: List documents is paginated and filterable

`GET /api/documents` SHALL require `installation_id` and SHALL return a paginated list. The system SHALL support optional filters `status` and `file_type`, and pagination parameters `page` and `page_size`.

#### Scenario: List for one installation

- **WHEN** a client requests `GET /api/documents` with an `installation_id` that has documents
- **THEN** the API returns only those documents and pagination metadata

#### Scenario: Filter by status

- **WHEN** a client requests the list with `status=PENDING`
- **THEN** the API returns only documents in that status for the installation

### Requirement: Get document includes chunks

`GET /api/documents/{id}` SHALL return the document and its chunks. When no chunks exist, the chunks list SHALL be empty. A missing id SHALL return 404.

#### Scenario: Get after upload

- **WHEN** a client fetches a document that was just uploaded
- **THEN** the API returns the document fields and `chunks` as an empty list

#### Scenario: Missing document

- **WHEN** a client fetches an unknown document id
- **THEN** the API returns 404

### Requirement: Delete removes document and chunks

`DELETE /api/documents/{id}` SHALL delete the document and all of its chunks in one database transaction via `ON DELETE CASCADE`. The stored file SHALL be removed when present. A missing id SHALL return 404. A successful delete SHALL return 204.

#### Scenario: Delete with chunks

- **WHEN** a document that has chunk rows is deleted
- **THEN** the document and those chunks are gone from the database and a second delete returns 404

#### Scenario: Delete uploaded file

- **WHEN** a document that has a file on disk is deleted
- **THEN** the API returns 204 and the file is no longer on disk

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
