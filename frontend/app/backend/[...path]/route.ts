import { getApiBaseUrl } from "@/src/lib/api-base";
import {
  INTERNAL_TOKEN_HEADER,
  internalTokenHeaders,
} from "@/src/lib/internal-token";
import { getSession } from "@/src/lib/session";

/** Гостевой чат и health доступны без сессии, всё остальное — только админке. */
const PUBLIC_PATHS = new Set(["chat", "health"]);

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

async function proxy(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const route = path.join("/");
  if (!PUBLIC_PATHS.has(route) && !(await getSession())) {
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
