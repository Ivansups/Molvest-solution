import { fetchAdminApi } from "@/src/lib/admin-api";
import type { DocumentListOut } from "@/src/types/api";
import { getApiBaseUrl } from "@/src/lib/api-base";

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
    (async () => {
      try {
        const response = await fetchAdminApi(`/api/documents?${query.toString()}`);
        if (!response.ok) {
          return {
            ok: false as const,
            message: "Не удалось загрузить список документов.",
          };
        }
        return {
          ok: true as const,
          data: (await response.json()) as DocumentListOut,
        };
      } catch {
        return {
          ok: false as const,
          message: "Не удалось загрузить список документов.",
        };
      }
    })(),
  ]);

  return { health, documents };
}
