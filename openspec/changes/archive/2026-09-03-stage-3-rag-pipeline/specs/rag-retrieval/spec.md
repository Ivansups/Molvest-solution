## Purpose

Searches indexed knowledge-base chunks by embedding similarity so the agent can ground its replies in retrieved content.

## ADDED Requirements

### Requirement: Query is embedded and nearest chunks returned

The system SHALL embed a query with the embeddings provider and return the top-K chunks ordered by cosine distance in `pgvector`. The number of results SHALL be configurable via application settings (`top_k`).

#### Scenario: Return nearest chunks for a query

- **WHEN** a query is issued against an indexed knowledge base
- **THEN** the system returns the chunks whose embeddings are nearest to the query embedding, up to `top_k` results, ordered by similarity

#### Scenario: Empty knowledge base returns no chunks

- **WHEN** a query is issued but no relevant indexed chunks exist
- **THEN** the system returns an empty result set

### Requirement: Retrieval is scoped to one installation

Retrieval SHALL only consider chunks belonging to documents of the caller's installation. Chunks from other installations SHALL never be returned.

#### Scenario: Chunks scoped by installation

- **WHEN** a query is issued for one installation
- **THEN** retrieved chunks belong only to documents of that installation, never to other installations

### Requirement: Only indexed documents are searchable

Retrieval SHALL match chunks whose document status is `INDEXED`. Chunks of documents with any other status (for example `PENDING` or a failed status) SHALL be excluded from results.

#### Scenario: Pending document chunks are excluded

- **WHEN** a query is issued while an installation has documents that are not yet indexed
- **THEN** those non-indexed documents' chunks are not returned, only chunks of `INDEXED` documents are considered

### Requirement: Agent receives retrieved context for generation

The agent graph SHALL perform retrieval for the target installation before generating a reply and SHALL pass the retrieved chunks, together with source references, into the generation prompt.

#### Scenario: Query is answered with retrieved context

- **WHEN** a chat request is processed for an installation that has indexed documents
- **THEN** the agent retrieves relevant chunks and the generated reply is grounded in those chunks' content

#### Scenario: No retrieved context yields no sources

- **WHEN** a chat request is processed but retrieval returns no chunks
- **THEN** the reply is generated without sources and the response lists no source references
