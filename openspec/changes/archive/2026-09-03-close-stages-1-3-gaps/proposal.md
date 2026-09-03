## Why

Stages 1–3 have a working RAG core, but several contract gaps block a live demo: upload does not index, guest chat searches a different installation than the admin, greetings call GigaChat, classify drops real 1C questions, answer cache sits after retrieve, and generate ignores saved history. FastAPI is also open and returns unstructured errors while the frontend/auth work proceeds in parallel.

## What Changes

- Protect domain FastAPI routes with `INTERNAL_SERVICE_TOKEN`. The token is still required if the UI later uses tRPC: tRPC is browser ↔ Next.js; FastAPI stays a separate service and must trust only the Next.js server. Browser and tRPC clients never receive the token. `/health` stays open for Compose checks. Empty token in local `.env` skips the check so Swagger and pytest keep working.
- Add a single JSON error envelope (`error`, `detail`, `request_id`) for unhandled and HTTP errors. Keep existing `request_id` logging.
- Start background indexing on `POST /api/documents` (same path as reindex). Response stays `201` + `PENDING`; status becomes `INDEXED` or `FAILED` after the task.
- Align guest `workspace_id` with the admin installation so uploaded documents are searchable from `/chat`.
- Classify support phrases before greetings. Greeting / thanks / empty use a template and do not call GigaChat.
- Check the Redis answer cache after classify and before retrieve. Do not cache greetings or escalations.
- Pass the last 3–4 persisted messages into `generate` for follow-up questions.
- Compress guest screenshots on the client and raise the chat request timeout so Vision can finish.
- In `docs/ROADMAP.md` set chunk embedding size to `vector(1024)`. No extra comment.

**Out of scope:** NextAuth, Prisma, login UI (separate frontend work). Bitrix/email channels. SSE `/chat/stream`. New metrics formulas.

## Capabilities

### New Capabilities

- `service-to-service-auth`: FastAPI checks the internal token on domain routes; Next.js injects it on the server-to-API hop.
- `api-error-envelope`: one JSON shape for FastAPI failures, including `request_id`.
- `agent-dialog-graph`: classify order, template greetings, answer-cache placement, history in generate.

### Modified Capabilities

- `knowledge-base-documents`: upload queues background indexing instead of leaving the document idle.
- `guest-chat-ui`: shared workspace id, screenshot compression, longer chat timeout.

## Impact

- Backend: `app/main.py`, new auth/error modules, `api/documents.py`, `services/documents.py`, `agent/graph.py`, `agent/nodes/classify.py`, `agent/nodes/generate.py`, `services/agent.py`, `docs/ROADMAP.md`, `server/app/models/chunk.py` comment.
- Frontend: Next.js rewrite or server fetch adds the token; `chat-page.tsx` workspace id, compression, axios timeout.
- Tests: token present/absent, error envelope, upload starts index, classify/greeting/cache/history, guest workspace matches admin.
- No new Python packages. Optional small frontend compression helper (canvas), no new npm dependency unless already present.
