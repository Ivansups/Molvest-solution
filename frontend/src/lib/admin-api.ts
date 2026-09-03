import "server-only";

import { getApiBaseUrl } from "@/src/lib/api-base";
import { toUserSession } from "@/src/lib/auth-user";
import { INTERNAL_TOKEN_HEADER } from "@/src/lib/internal-token";
import type { UserSession } from "@/src/types/domain";

export async function requireAuthenticatedUser(): Promise<UserSession | null> {
  const { auth } = await import("@/auth");
  return toUserSession(await auth());
}

function getInternalServiceToken(): string {
  const token = process.env.INTERNAL_SERVICE_TOKEN?.trim();
  if (!token) {
    throw new Error("INTERNAL_SERVICE_TOKEN is not set");
  }
  return token;
}

export async function fetchAdminApi(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getInternalServiceToken();
  headers.set(INTERNAL_TOKEN_HEADER, token);

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
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
