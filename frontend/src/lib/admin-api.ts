import "server-only";

import { getApiBaseUrl } from "@/src/lib/api-base";
import { toUserSession } from "@/src/lib/auth-user";
import { internalTokenHeaders } from "@/src/lib/internal-token";
import type { UserSession } from "@/src/types/domain";

export async function requireAuthenticatedUser(): Promise<UserSession | null> {
  const { auth } = await import("@/auth");
  return toUserSession(await auth());
}

export async function fetchAdminApi(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  // Пустой INTERNAL_SERVICE_TOKEN — штатная локальная конфигурация:
  // backend в этом случае проверку не требует.
  const headers = new Headers(init?.headers);
  for (const [name, value] of Object.entries(internalTokenHeaders())) {
    headers.set(name, value);
  }

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(10_000),
  });
}

export async function proxyAdminApi(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const upstream = await fetchAdminApi(path, init);
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const requestId = upstream.headers.get("x-request-id");

  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (requestId) {
    headers.set("x-request-id", requestId);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
