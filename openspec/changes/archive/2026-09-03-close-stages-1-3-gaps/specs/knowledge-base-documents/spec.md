## MODIFIED Requirements

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
