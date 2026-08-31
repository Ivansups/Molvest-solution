## Purpose

Chunks and embeds knowledge-base documents into vector storage so the agent can retrieve grounded context for answers.

## ADDED Requirements

### Requirement: Text is extracted from supported file types

The system SHALL extract plain text from PDF, DOCX, HTML, and MD uploads. Extraction SHALL be performed off the event loop (non-blocking). Unreadable or unsupported content SHALL lead the index attempt to fail and the document SHALL be marked with a failed status.

#### Scenario: Text extracted from markdown

- **WHEN** a document with a supported file type is indexed
- **THEN** the system reads the file content and uses it for chunking

#### Scenario: Indexing failure marks document failed

- **WHEN** text extraction or embedding fails during indexing
- **THEN** the document status is set to a failed status and no partial chunks are persisted

### Requirement: Document is split into word-based chunks with overlap

The system SHALL split extracted text into chunks of at most `max_chunk_size` words, reusing `chunk_overlap` words between adjacent chunks. Chunking parameters SHALL be configurable via application settings.

#### Scenario: Short document becomes a single chunk

- **WHEN** a document's text is shorter than the maximum chunk size
- **THEN** the system produces exactly one chunk containing the full text

#### Scenario: Long document is split with overlap

- **WHEN** a document's text exceeds the maximum chunk size
- **THEN** the system produces multiple chunks and adjacent chunks share the configured overlap

### Requirement: Index atomically replaces chunks and sets status

Indexing a document SHALL delete all of that document's existing chunks and insert the newly built chunks within a single database transaction, then set the document status to `INDEXED`. Retrieval SHALL never observe a half-updated document.

#### Scenario: Atomic replace of an existing indexed document

- **WHEN** a previously indexed document is re-indexed
- **THEN** the new chunks replace the old ones and the document status is `INDEXED` without ever exposing a mixed set of old and new chunks

#### Scenario: First index sets indexed status

- **WHEN** a pending document is indexed for the first time
- **THEN** the document status is set to `INDEXED` and retrieval can find its chunks

### Requirement: Embeddings are computed before the transaction

The system SHALL request embeddings only after chunking and SHALL complete the GigaChat embedding call before opening the database transaction that persists chunks. A failure to obtain embeddings SHALL NOT leave partial chunk rows.

#### Scenario: Embedding failure prevents partial state

- **WHEN** the embeddings provider fails
- **THEN** the indexing attempt aborts, no chunks are written, and the document is marked failed
