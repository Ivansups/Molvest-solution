import type { DocumentListOut } from "@/src/types/api";

function apiBase(): string {
  return (process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

export type ServerResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string };

export async function serverFetchJson<T>(
  path: string,
  fallback: string,
): Promise<ServerResult<T>> {
  try {
    const response = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
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
