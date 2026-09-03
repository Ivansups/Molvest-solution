import type { DocumentListOut } from "@/src/types/api";
import { getApiBaseUrl } from "@/src/lib/api-base";
import { internalTokenHeaders } from "@/src/lib/internal-token";

export type ServerResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string };

export async function serverFetchJson<T>(
  path: string,
  fallback: string,
): Promise<ServerResult<T>> {
  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: internalTokenHeaders(),
    });
    if (!response.ok) {
      return { ok: false, message: fallback };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, message: fallback };
  }
}

export async function loadDashboard(installationId: string): Promise<{
  health: ServerResult<{ status: string }>;
  documents: ServerResult<DocumentListOut>;
}> {
  const query = new URLSearchParams({
    installation_id: installationId,
    page: "1",
    page_size: "20",
  });

  const [health, documents] = await Promise.all([
    serverFetchJson<{ status: string }>(
      "/health",
      "Не удалось получить статус backend /health.",
    ),
    serverFetchJson<DocumentListOut>(
      `/api/documents?${query.toString()}`,
      "Не удалось загрузить список документов.",
    ),
  ]);

  return { health, documents };
}
