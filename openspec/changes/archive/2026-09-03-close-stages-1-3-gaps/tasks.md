## 1. Docs and constants

- [x] 1.1 In `docs/ROADMAP.md` replace `vector(1536)` with `vector(1024)`
- [x] 1.2 In `server/app/models/chunk.py` drop the “not 1536” aside; keep `EMBEDDING_DIMENSIONS = 1024`

## 2. Service token and error envelope

- [x] 2.1 Add a FastAPI dependency that checks `X-Internal-Token` when `INTERNAL_SERVICE_TOKEN` is set; skip `/health`, `/docs`, `/openapi.json`, `/redoc`
- [x] 2.2 Register the dependency on domain routers (`/chat`, `/api/documents`, `/api/conversations`, `/api/metrics`)
- [x] 2.3 Add exception handlers that return `{error, detail, request_id}` for HTTP and unhandled errors
- [x] 2.4 Inject `X-Internal-Token` on the Next.js `/backend` hop from `INTERNAL_SERVICE_TOKEN`; do not expose it to the browser
- [x] 2.5 Tests: 401 without token when configured; 200 `/health` without token; empty token skips check; error body has `request_id`

## 3. Upload indexes in the background

- [x] 3.1 After a successful `POST /api/documents`, start the same background reindex task as `POST …/reindex`
- [x] 3.2 Test: upload returns `201` `PENDING` and indexing is invoked for that document id

## 4. Agent graph

- [x] 4.1 Classify: empty → greeting keywords only after support keywords; templates for `empty`, `greeting`, `off_topic`
- [x] 4.2 End the graph after classify for `empty`, `greeting`, and `off_topic` (no `generate`)
- [x] 4.3 After classify, on `support`, read the answer cache; hit skips retrieve and generate
- [x] 4.4 Write the answer cache only after a non-escalated generate
- [x] 4.5 If `workspace_id` is a UUID, use it as `installation_id`; otherwise keep `uuid5`
- [x] 4.6 Load last 3–4 messages in `run_chat_turn` and pass them into `generate`; do not store raw image base64 in `image_url`
- [x] 4.7 Tests: «привет, как провести документ» → support; «привет» / empty / off-topic skip GigaChat; weak score still escalates without generate; cache hit skips generate; follow-up prompt includes prior messages; UUID workspace is not hashed

## 5. Guest chat

- [x] 5.1 Send the admin installation UUID as guest `workspace_id`
- [x] 5.2 Resize attached screenshots (long side ≤ 1024) before `image_base64`
- [x] 5.3 Set the chat request timeout to at least 60 seconds
- [x] 5.4 Frontend lint and typecheck

## 6. Quality gate

- [x] 6.1 `cd server && uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- [x] 6.2 `cd server && uv run pytest`
- [x] 6.3 `pnpm --dir frontend lint && pnpm --dir frontend typecheck`
