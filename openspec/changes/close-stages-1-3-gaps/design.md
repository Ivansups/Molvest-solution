## Context

Stages 1–3 already have FastAPI, document CRUD, LangGraph (vision → classify → retrieve → generate), persist, and a guest widget. The remaining gaps are contract mismatches, not a new product slice. NextAuth and Prisma are being built on the frontend in parallel and stay out of this change.

tRPC on the frontend (if added later) does not remove the internal token. tRPC covers browser ↔ Next.js. FastAPI is still a second process. Only the Next.js server may call it after attaching `INTERNAL_SERVICE_TOKEN`. FastAPI still does not parse NextAuth cookies.

## Goals / Non-Goals

**Goals:**

- Close FastAPI from the open internet when the token is set, without breaking `/health` or empty-token local/dev.
- Return one JSON error shape with `request_id`.
- Index on upload in the background.
- Make guest search see admin-uploaded documents.
- Greeting/thanks/empty never call GigaChat; support phrases win over greetings.
- Answer cache after classify, before retrieve; no cache for greetings or escalations.
- Generate sees the last 3–4 saved messages.
- Guest screenshots are compressed; chat waits long enough for Vision.
- Roadmap embedding size is `vector(1024)`.

**Non-Goals:**

- NextAuth, Prisma, login page, admin middleware.
- tRPC itself.
- SSE `/chat/stream`.
- Bitrix/email channels.
- Changing embedding dimension in Postgres (already 1024).

## Decisions

### 1. Token header, not NextAuth on FastAPI

- Header: `X-Internal-Token`.
- If `settings.internal_service_token` is empty, skip the check (local pytest, Swagger, `make api` without a secret).
- If set, require an exact match on all routes except `/health`, `/docs`, `/openapi.json`, `/redoc`.
- Next.js injects the header on the server hop: middleware (or the `/backend` proxy) reads `INTERNAL_SERVICE_TOKEN` from env and sets `X-Internal-Token`. The browser never sees the value.
- Same rule if the UI later uses tRPC: tRPC procedures on the Next.js server attach the header when they call FastAPI.

Alternatives: put NextAuth JWT validation in FastAPI (rejected — roadmap and current frontend work keep auth on Next.js). Leave FastAPI open (rejected — token is already in `.env.example`).

### 2. One error envelope

Unhandled exceptions and `HTTPException` return:

```json
{"error": "http_error|internal_error", "detail": "...", "request_id": "..."}
```

`request_id` is the existing context var / `x-request-id` header. FastAPI validation errors (`422`) keep the same envelope; `detail` may be a string summary.

### 3. UUID workspace is used as-is

`workspace_to_installation_id` today always hashes via `uuid5`, so a guest string never matches the admin `installation_id`. If `workspace_id` is a valid UUID, use it directly. Otherwise keep `uuid5`. Guest chat sends the same id the admin session already uses (`7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11`).

### 4. Upload queues the existing reindex task

`POST /api/documents` stays `201` + `PENDING` after the file is on disk. The route adds the same `BackgroundTasks` helper as `POST …/reindex`. No Celery. Failed index marks `FAILED` as today.

### 5. Classify: support first, then greeting, then off-topic

Empty query → template, end. If support keywords match → `support` even when the text also says «привет». Else if greeting/thanks match → template, end, no GigaChat. Else `off_topic` → short template, no GigaChat (same budget as greeting: no model call).

Templates live next to the existing empty-reply constant. The graph ends after classify for `empty`, `greeting`, and `off_topic`.

### 6. Answer cache as a graph branch, not inside generate

After classify, if intent is `support`, look up `ans:{kb_version}:{hash(query)}`. Hit → fill `answer` / `sources` if stored, skip retrieve and generate. Miss → retrieve. After a successful generate (not escalated), write the cache. Do not write on greeting/off-topic/empty (those no longer generate) and do not write escalations (graph never reaches generate).

Current cache stores only the answer string. Keep that: a cache hit returns the text; `sources` may be empty on a hit unless we already store them. Do not expand the Redis value format in this change.

### 7. History is loaded in `run_chat_turn`, not in graph nodes

Before `ainvoke`, load the last 3–4 messages of the conversation (if `conversation_id` exists) and put them on `AgentState`. `generate` appends them to the user prompt. Graph nodes still do not open a DB session.

### 8. Screenshots: compress on client, do not store raw base64 as `image_url`

Canvas resize, long side ≤ 1024, then strip the data-URL prefix (existing contract). Axios timeout for chat becomes 60s. Persist writes `image_url=None` (or omits the payload); the raw base64 is not stored in `messages.image_url`.

### 9. Docs

Replace `vector(1536)` with `vector(1024)` in `docs/ROADMAP.md`. Drop the “not 1536” aside in `chunk.py`; leave the dimension constant as-is.

## Risks / Trade-offs

- [Empty token in production] → Compose `.env.example` already has the key; document that a non-empty value is required when the API is reachable outside Docker’s internal network.
- [Rewrite does not forward middleware headers] → If Next.js rewrite drops `X-Internal-Token`, switch the proxy to a server route that `fetch`es FastAPI with the header.
- [Cache hit without sources] → Acceptable; kb_version still invalidates text when documents change.
- [Off-topic is now a template] → Slightly drier replies, one fewer GigaChat call. Matches the latency budget.
- [Background index after upload] → Admin must poll or refresh to see `INDEXED`. Same as today’s manual reindex.

## Migration Plan

1. Ship backend token check with empty default (no lockout).
2. Inject the header from Next.js; set `INTERNAL_SERVICE_TOKEN` in Compose `.env`.
3. Align guest workspace id and UUID passthrough together so search does not go empty.
4. Enable upload→index after the reindex background path is reused.
5. Rollback: unset `INTERNAL_SERVICE_TOKEN` and revert the graph/classify files.

## Open Questions

None. tRPC does not change the token decision. NextAuth stays on the frontend track.
