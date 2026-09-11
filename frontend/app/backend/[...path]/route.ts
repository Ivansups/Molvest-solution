import { getApiBaseUrl } from "@/src/lib/api-base";
import {
  INTERNAL_TOKEN_HEADER,
  internalTokenHeaders,
} from "@/src/lib/internal-token";
import { getSession } from "@/src/lib/session";

/** Гостевой чат и health доступны без сессии, всё остальное — только админке. */
const PUBLIC_PATHS = new Set(["chat", "health"]);

const CONVERSATION_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function copyHopSafe(source: Headers): Headers {
  const headers = new Headers();
  source.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  return headers;
}

function isGuestConversationPoll(method: string, path: string[]): boolean {
  return (
    method === "GET" &&
    path.length === 3 &&
    path[0] === "api" &&
    path[1] === "conversations" &&
    CONVERSATION_ID.test(path[2] ?? "")
  );
}

/** Черновик и комментарий закрытия — только оператору, не гостевому poll. */
const GUEST_HIDDEN_FIELDS = [
  "suggested_response",
  "resolve_comment",
  "resolve_confirmed_at",
] as const;

async function stripOperatorOnlyFields(upstream: Response): Promise<Response> {
  const headers = copyHopSafe(upstream.headers);
  headers.delete("content-length");
  const contentType = upstream.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  }
  const payload: unknown = await upstream.json();
  if (payload !== null && typeof payload === "object" && !Array.isArray(payload)) {
    const body = { ...(payload as Record<string, unknown>) };
    for (const field of GUEST_HIDDEN_FIELDS) {
      delete body[field];
    }
    return Response.json(body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  }
  return Response.json(payload, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const route = path.join("/");
  const session = await getSession();
  const guestPoll = isGuestConversationPoll(request.method, path);
  if (!PUBLIC_PATHS.has(route) && !guestPoll && !session) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const incoming = new URL(request.url);
  const target = `${getApiBaseUrl()}/${route}${incoming.search}`;

  const headers = copyHopSafe(request.headers);
  // Служебный токен ставит только прокси — присланный браузером не в счёт.
  headers.delete(INTERNAL_TOKEN_HEADER);
  for (const [key, value] of Object.entries(internalTokenHeaders())) {
    headers.set(key, value);
  }

  const method = request.method;
  const body =
    method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();

  const upstream = await fetch(target, {
    method,
    headers,
    body,
    cache: "no-store",
    redirect: "manual",
  });

  if (guestPoll && !session) {
    return stripOperatorOnlyFields(upstream);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: copyHopSafe(upstream.headers),
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
