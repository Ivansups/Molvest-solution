## Why

Stage 3 of the roadmap turns the knowledge base from a passive store (Stage 2) into a real RAG pipeline. Today documents are stored with status `PENDING`, reindex is a no-op reset, and retrieval returns nothing, so the agent answers with no grounding. Without chunking, vector indexing, and retrieval, the agent cannot answer 1C support questions from the knowledge base — the core value of the product.

## What Changes

- Add word-based chunking with overlap (`max_chunk_size=512`, `chunk_overlap=128`) and text extraction for PDF, DOCX, HTML, and MD.
- Index a document: extract text, split into chunks, embed them via GigaChat `Embeddings`, and atomically replace the document's chunks while setting its status to `INDEXED` in one database transaction.
- Retrieve the top-K chunks for a query by cosine distance (`pgvector`), scoped to a single installation and only `INDEXED` documents.
- Wire a `retrieve` node into the LangGraph agent; the graph passes retrieved chunks into the prompt for grounded generation.
- Replace the reindex no-op with a real reindex (re-chunk + re-embed + atomic replace).
- Add a deterministic `workspace_id -> installation_id` mapping so chat stays on the existing `/chat` contract.

## Capabilities

### New Capabilities

- `rag-ingestion`: Chunking, text extraction, and atomic index/reindex of a knowledge-base document with GigaChat embeddings.
- `rag-retrieval`: Vector search over `INDEXED` chunks, scoped by installation, returning the top-K nearest chunks.

### Modified Capabilities

- `knowledge-base-documents`: reindex is no longer a no-op reset; it performs a real reindex and returns the document with chunks.

## Impact

- New: `server/app/rag/chunking.py`, `server/app/rag/ingestion.py`, `server/app/rag/retrieval.py`, `server/app/rag/protocols.py`, `server/app/agent/nodes/retrieve.py`, `server/tests/test_rag.py`.
- Touched: `server/app/agent/graph.py`, `server/app/agent/state.py`, `server/app/services/agent.py`, `server/app/services/documents.py`, `server/app/api/documents.py`, `server/app/core/config.py`.
- Dependencies: `pypdf`, `python-docx`.
- Out of scope: chat HTTP persistence, audit logging of escalations beyond the existing service, admin UI, answer source citation UI.
