## Why

Stage 2 of the roadmap is the storage layer for the knowledge base and conversations. Without tables, migrations, and document CRUD, RAG retrieval stays a stub and the admin UI has nothing to call. Stage 1 is in place; this change unblocks Stage 3.

## What Changes

- Add SQLAlchemy models: Document, Chunk, Conversation, Message, Escalation.
- Add the first Alembic migration (including `pgvector` and a `vector` column on chunks).
- Add document admin services and REST routes for list, upload, get, delete, and reindex.
- Persist uploaded files and document metadata with status `PENDING`. Real chunking and embeddings stay out of scope (Stage 3).
- Reindex exists as an API that resets the document to `PENDING` and is otherwise a no-op until Stage 3.
- Conversation / message / escalation tables are created now. Chat still does not write to them in this change.

## Capabilities

### New Capabilities

- `knowledge-base-documents`: Document and Chunk storage, upload/list/get/delete/reindex API, cascade delete of chunks.
- `conversation-records`: Conversation, Message, and Escalation tables plus a single status-transition service. No public conversation API in this change.

### Modified Capabilities

- None. There are no existing specs.

## Impact

- New: `server/app/models/`, `server/app/db/`, document router/schemas/services/selectors, Alembic revision.
- Touched: `server/alembic/env.py` (`target_metadata`), `server/app/main.py` (register documents router).
- Tests: upload (PDF/DOCX), cascade delete, duplicate `file_name` per installation, delete removes chunks.
- Out of scope: indexing, GigaChat embeddings, chat persistence, admin UI, conversation HTTP API.
