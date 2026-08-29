## 1. Database session and dependencies

- [x] 1.1 Add `python-multipart` with `uv add` (file uploads)
- [x] 1.2 Add `app/db/base.py` with shared `DeclarativeBase`
- [x] 1.3 Add `app/db/session.py` with async engine, `async_sessionmaker`, and FastAPI session dependency
- [x] 1.4 Add `upload_dir` to `Settings` (default `./data/uploads`)

## 2. Domain models

- [x] 2.1 Add Document and Chunk models with enums, `vector(1024)` embedding, and `uq_documents_installation_id_file_name`
- [x] 2.2 Add Conversation, Message, and Escalation models with UTC timestamps and named FKs/indexes
- [x] 2.3 Wire all models so Alembic metadata includes every table

## 3. Migration

- [x] 3.1 Point `alembic/env.py` `target_metadata` at `Base.metadata`
- [x] 3.2 Generate the first revision: `CREATE EXTENSION vector` plus the five tables
- [x] 3.3 Confirm `alembic upgrade head` applies on the Compose Postgres

## 4. Conversation status

- [x] 4.1 Add a transition service that allows only `open → escalated` and `escalated → resolved`
- [x] 4.2 Unit-test legal and illegal transitions (including `open → resolved`)

## 5. Document write and read paths

- [x] 5.1 Add document schemas for create/list/detail/reindex responses
- [x] 5.2 Add selectors: list (filters + pagination) and get-by-id with chunks
- [x] 5.3 Add upload service: validate type, persist `PENDING` row, write file after commit, 409 on duplicate name
- [x] 5.4 Add delete service: cascade chunks, remove file, 404 if missing
- [x] 5.5 Add reindex service: set `PENDING`, do not touch chunks, 404 if missing

## 6. Documents API

- [x] 6.1 Add `app/api/documents.py` for `GET/POST /api/documents`, `GET/DELETE /api/documents/{id}`, `POST /api/documents/{id}/reindex`
- [x] 6.2 Register the router in `main.py`
- [x] 6.3 Confirm routes appear in OpenAPI (`/docs`)

## 7. Tests

- [x] 7.1 Add async HTTP fixtures against Postgres (`httpx` + `DATABASE_URL`)
- [x] 7.2 Test PDF and DOCX upload → `PENDING`, file on disk
- [x] 7.3 Test unsupported type → 422 and no row
- [x] 7.4 Test duplicate `file_name` in the same installation → 409; same name in another installation succeeds
- [x] 7.5 Test list filters and get-after-upload (empty chunks)
- [x] 7.6 Test delete: cascade chunks, file gone, second delete → 404
- [x] 7.7 Test reindex twice → both succeed, status stays `PENDING`
- [x] 7.8 Confirm `POST /chat` contract is unchanged

## 8. Quality gate

- [x] 8.1 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy .` in `server/` and fix all findings
- [x] 8.2 Run `uv run pytest` and fix failures
