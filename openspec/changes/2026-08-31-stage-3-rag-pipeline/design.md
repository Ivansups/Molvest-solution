## Context

Stage 2 provided document/chunk storage and `POST /api/documents/{id}/reindex` as a no-op reset. There is no chunking, no embedding, and no retrieval. The LangGraph agent graph (`server/app/agent/graph.py`) currently classifies a query and replies without grounding. GigaChat embeddings are exposed on `GigaChatService.get_embeddings` (model `Embeddings`, 1024 dims). See proposal.md — Why for motivation; the specs define the required behavior.

## Goals / Non-Goals

**Goals:**
- Atomic index/reindex: a document's chunks are replaced and its status updated in one DB transaction so retrieval never sees a half-updated document.
- Retrieval scoped by installation over `INDEXED` chunks only, ordered by cosine distance, capped by `top_k`.
- The agent graph gains a `retrieve` node that feeds chunks into generation.
- External GigaChat embedding calls happen outside the DB transaction (states are committed first, then the external API is called).

**Non-Goals:**
- Reranking, hybrid (lexical + vector) search, or answer source-citation UI.
- Cross-installation or global (non-scoped) search.
- Streaming tokens or chat persistence changes (handled by later stages).

## Decisions

### Decision 1: Word-count chunker instead of token-based

Chunking counts words, not LLM tokens, so a document of `N` words becomes chunks of `max_chunk_size` words reusing `chunk_overlap` words between adjacent chunks. It needs no tokenizer dependency and is stable for short 1C support documents.

- **Alternative considered**: tokenizer-based splitting (e.g., a BPE tokenizer). Rejected — adds a dependency and the embedding model's tokenization is internal to GigaChat anyway.
- **Consequence**: chunk boundaries are word-aligned, which is fine for the current corpus.

### Decision 2: Embeddings before the DB transaction; atomic replace inside it

`index_document` reads and extracts text (off the event loop via `asyncio.to_thread`), runs chunking, then calls the embedding provider; only after embeddings succeed does it open the transaction that deletes the document's old chunks, inserts the new ones, and sets status to `INDEXED`. On any failure before commit, nothing is persisted and the document is marked failed.

- **Why**: embeds the external-call-outside-transaction invariant from AGENTS.md, and makes re-index atomic (delete + insert + status in one transaction).
- **Alternative considered**: writing status/chunks incrementally. Rejected — would expose partial state and violate the atomicity invariant.

### Decision 3: Retriever as a callable + `EmbeddingsProvider` protocol for testability

The graph node depends on a `Retriever` (`Callable[[AgentState], Awaitable[list[RetrievedChunk]]]`), keeping it pure and unit-testable. Production wiring uses `make_retriever`, which opens a `SessionLocal()` per call and embeds the query through `EmbeddingsProvider`. `EmbeddingsProvider` is a structural Protocol so tests inject a deterministic fake embedder instead of hitting GigaChat.

- **Why**: separates graph wiring from DB/embedding concerns and lets the whole pipeline be tested without network access.

### Decision 4: Deterministic `workspace_id -> installation_id` mapping

Chat keeps its existing `/chat` contract; the agent resolves the target knowledge base through a deterministic UUID5 mapping from `workspace_id` to `installation_id` (fixed namespace), so no new chat request field is required.

- **Alternative considered**: adding an explicit `installation_id` to the chat request. Rejected — would change the public contract and break the frontend.
- **Consequence**: a given `workspace_id` always maps to the same installation, which matches how documents are uploaded.

### Decision 5: Vector search with `pgvector` cosine distance

Retrieval embeds the query and orders `Chunk.embedding` by `cosine_distance`, filtering by installation and `INDEXED` status, then `LIMIT top_k`. `top_k`, `max_chunk_size`, and `chunk_overlap` are application settings.

- **Alternative considered**: exact/brute-force over all chunks. `pgvector` already provides the operator and an index path; no additional search dependency is introduced.

## Risks / Trade-offs

- [Embedding cost / 402 if embeddings not enabled in GigaChat account] → embeddings are a separately billed endpoint; the pipeline handles provider failure by failing the index attempt and marking the document failed rather than writing partial chunks. Ensure the GigaChat account has the embeddings scope before enabling automated indexing.
- [Latency of embedding calls in the request path] → indexing/reindex is an explicit operator action (not on the chat hot path); retrieval embeds only the query of `top_k` small.
- [Crash between DB commit and external side effects] → embeddings happen before the transaction, so a crash cannot persist chunks without their embeddings or leave partial state.
- [Cosine distance only, no lexical fallback] → acceptable for the current corpus; a hybrid reranker is a possible later addition without changing the spec contract.

## Migration Plan

No data migration: existing documents sit at `PENDING` with no chunks. Deploy applies the existing schema (already in place); the new behavior affects only `INDEXED` documents going forward. Reindexing existing documents one by one via `POST /api/documents/{id}/reindex` upgrades them to `INDEXED`. Rollback: revert code only; chunks and status are ordinary rows, no schema change to undo.

## Open Questions

None — behavior, approach, and task breakdown are fully determined by the proposal and specs.
