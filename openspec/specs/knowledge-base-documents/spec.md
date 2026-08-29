## Purpose

Storage and admin API for knowledge-base documents and chunks. Indexing and embeddings are out of scope until a later change.

## Requirements

### Requirement: Document and chunk tables exist

The system SHALL persist Document and Chunk rows in PostgreSQL with the fields defined in roadmap Stage 2. Chunk.embedding SHALL be a nullable `vector(1024)` column (GigaChat `Embeddings`). The first Alembic revision SHALL enable the `vector` extension and create both tables. Indexes and constraints SHALL use names of the form `ix_<table>_<column>` and `uq_<table>_<column>`.

#### Scenario: Migration applies cleanly

- **WHEN** an operator runs Alembic upgrade to head against an empty database
- **THEN** Document and Chunk tables exist and the `vector` extension is enabled

### Requirement: Upload creates a pending document

The system SHALL accept `POST /api/documents` as multipart form data with `file`, `title`, and `installation_id`. Optional `metadata` MAY be a JSON object string. Allowed file types are PDF, DOCX, HTML, and MD. On success the system SHALL store the file on disk, persist a Document with status `PENDING`, and SHALL NOT create chunks or embeddings.

#### Scenario: Upload PDF

- **WHEN** a client uploads a PDF with a title and installation id
- **THEN** the API returns the document with status `PENDING` and the file is stored on disk

#### Scenario: Upload DOCX

- **WHEN** a client uploads a DOCX with a title and installation id
- **THEN** the API returns the document with status `PENDING` and the file is stored on disk

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

### Requirement: Reindex is a no-op reset

`POST /api/documents/{id}/reindex` SHALL set the document status to `PENDING` and SHALL NOT create, replace, or delete chunks. Calling it twice SHALL leave the document `PENDING`. A missing id SHALL return 404.

#### Scenario: Reindex pending document

- **WHEN** a client calls reindex on an existing document
- **THEN** the API returns the document with status `PENDING`

#### Scenario: Reindex is idempotent

- **WHEN** a client calls reindex twice on the same document
- **THEN** both calls succeed and the document status is `PENDING`
