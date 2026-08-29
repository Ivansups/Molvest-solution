## Context

Stage 1 left FastAPI, Postgres + pgvector, Alembic, and the `/chat` contract running. There are no SQLAlchemy models, no session factory, and `alembic/env.py` has `target_metadata = None`. The agent graph already exists, but `retrieve` returns an empty list until documents and chunks live in the database.

This change is the storage layer from roadmap Stage 2. Indexing and embeddings stay in Stage 3.

## Goals / Non-Goals

**Goals:**

- Persist Document, Chunk, Conversation, Message, Escalation with an explicit Alembic revision.
- Expose document CRUD over REST so Swagger can upload, list, fetch, delete, and request reindex.
- Delete a document and its chunks (and the vector column rows) in one transaction.
- Change `Conversation.status` only through one transition service.

**Non-Goals:**

- Chunking, GigaChat embeddings, or real reindex work.
- Writing chat turns into Conversation/Message.
- Admin UI, NextAuth, or `INTERNAL_SERVICE_TOKEN` checks on these routes.
- Changing `POST /chat` behavior.

## Decisions

### 1. One async session, models under `app/models/`

Add `app/db/base.py` (`DeclarativeBase`) and `app/db/session.py` (async engine + `async_sessionmaker`). Routers get a session via FastAPI `Depends`. Alembic imports the same `Base.metadata` so autogenerate sees all tables.

Alternative: one `models.py` file. Rejected — AGENTS.md wants one responsibility per file.

### 2. Roadmap columns, string enums, timezone-aware UTC

Keep the fields from the roadmap. Store enums as `VARCHAR` (`native_enum=False`) to avoid painful Alembic enum alters. All timestamps are `DateTime(timezone=True)` in UTC; API responses are ISO 8601 with offset.

`Chunk.embedding` is `Vector(1024)`, nullable — size of GigaChat `Embeddings`, not the 1536 from the roadmap (that number is OpenAI). Stage 2 never writes embeddings.

`Document` has no extra `storage_path` column. File location goes in `metadata["storage_path"]`.

Alternative: native PostgreSQL ENUMs. Rejected — migration cost without benefit at this size.

### 3. Files on disk, metadata in Postgres

`POST /api/documents` is `multipart/form-data`: `file`, `title`, `installation_id`, optional `metadata` JSON string.

Save bytes under `{upload_dir}/{installation_id}/{document_id}/{file_name}`. `upload_dir` is a settings field (default `./data/uploads`). Allowed types: PDF, DOCX, HTML, MD — inferred from extension; anything else is 422.

Need `python-multipart` (`uv add python-multipart`).

Alternative: store file bytes in the row. Rejected — bloated backups for no Stage 2 gain.

### 4. Duplicate name is a conflict, not a new version

Unique constraint `uq_documents_installation_id_file_name`. Second upload with the same `file_name` in the same installation returns **409**. No silent overwrite.

### 5. Routes match the roadmap; no auth yet

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/documents` | Paginated list. Required `installation_id`. Optional `status`, `file_type`, `page`, `page_size`. |
| POST | `/api/documents` | Create, status `PENDING`. Does not index. |
| GET | `/api/documents/{id}` | Document + chunks (empty until Stage 3). 404 if missing. |
| DELETE | `/api/documents/{id}` | Delete row (cascade chunks) and best-effort delete the file. **204**. Second call **404**. |
| POST | `/api/documents/{id}/reindex` | Set status `PENDING`, leave chunks as-is. Idempotent. Real work is Stage 3. |

Reads go through `selectors.py`. Writes go through `services/`. Router only validates and maps errors.

`installation_id` stays UUID (roadmap). Chat `workspace_id` is a string and is not mapped in this change.

Auth on these routes is a later stage. Do not add token checks now.

### 6. Conversation status has one door

`Conversation.status` MUST NOT be assigned in routers, channel adapters, or graph nodes. A small service accepts only:

`open → escalated → resolved`

Any other transition raises a domain error. No conversation HTTP API in this change.

### 7. Cascade delete is a database rule

`Chunk.document_id` is `ON DELETE CASCADE`. Deleting the document removes chunks and their embeddings in the same transaction. Application code does not delete chunks one by one.

### 8. Tests hit Postgres, not SQLite

pgvector is not useful on SQLite. Use the existing Compose Postgres (or `DATABASE_URL`) with `httpx.AsyncClient` and `pytest-asyncio`. Tests: upload PDF and DOCX; cascade delete; duplicate name → 409; reindex called twice stays `PENDING`.

## Risks / Trade-offs

- [Switching to EmbeddingsGigaR later] → That model is 2560. Would need a new migration and full reindex. Stay on `Embeddings` (1024) for the hackathon.
- [Orphan files if DB commit fails after a disk write] → Write the file after the row is committed, or delete the file if the transaction rolls back. Prefer commit-then-write; if write fails, mark `FAILED` or delete the row.
- [Open document API] → Acceptable for the hackathon until Next.js sends `INTERNAL_SERVICE_TOKEN`.
- [Reindex is a stub] → Document in OpenAPI description so it is not mistaken for Stage 3 indexing.

## Migration Plan

1. `CREATE EXTENSION IF NOT EXISTS vector` in the first revision.
2. Create the five tables with named indexes/constraints (`ix_<table>_<column>`, `uq_<table>_<column>`).
3. Point Alembic `target_metadata` at `Base.metadata`.
4. `make migrate` / `alembic upgrade head`.
5. Rollback: `alembic downgrade -1` drops the tables. Uploaded files on disk are not reverted automatically.

## Open Questions

None that block implementation. Embedding dimension is 1024 to match the GigaChat `Embeddings` model already used in `gigachat_client`.
