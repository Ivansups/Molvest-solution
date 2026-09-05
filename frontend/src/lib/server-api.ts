import { fetchAdminApi } from "@/src/lib/admin-api";
import type {
  ConversationListOut,
  ConversationMetrics,
  DocumentListOut,
} from "@/src/types/api";
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
      signal: AbortSignal.timeout(10_000),
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
  conversations: ServerResult<ConversationListOut>;
  metrics: ServerResult<ConversationMetrics>;
}> {
  const query = new URLSearchParams({
    installation_id: installationId,
    page: "1",
    page_size: "20",
  });

  const [health, documents, conversations, metrics] = await Promise.all([
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
    serverFetchJson<ConversationListOut>(
      `/api/conversations?${query.toString()}`,
      "Не удалось загрузить последние диалоги.",
    ),
    serverFetchJson<ConversationMetrics>(
      `/api/metrics?installation_id=${encodeURIComponent(installationId)}`,
      "Не удалось загрузить метрики диалогов.",
    ),
  ]);

  return { health, documents, conversations, metrics };
}

export async function loadAnalytics(installationId: string): Promise<{
  metrics: ServerResult<ConversationMetrics>;
  trends: Array<{
    date: string;
    tickets: number;
    autoReplies: number;
    escalations: number;
  }>;
}> {
  const today = new Date();
  const dailyQueries = Array.from({ length: 7 }, (_, index) => {
    const start = new Date(today);
    start.setUTCDate(today.getUTCDate() - (6 - index));
    start.setUTCHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setUTCDate(start.getUTCDate() + 1);

    const dateQuery = new URLSearchParams({
      installation_id: installationId,
      date_from: start.toISOString(),
      date_to: end.toISOString(),
    });
    const conversationQuery = new URLSearchParams({
      ...Object.fromEntries(dateQuery),
      page: "1",
      page_size: "1",
    });
    return { date: start.toISOString().slice(0, 10), dateQuery, conversationQuery };
  });

  const [metrics, ...dailyData] = await Promise.all([
    serverFetchJson<ConversationMetrics>(
      `/api/metrics?installation_id=${encodeURIComponent(installationId)}`,
      "Не удалось загрузить метрики диалогов.",
    ),
    ...dailyQueries.map(async ({ date, dateQuery, conversationQuery }) => {
      const [dailyMetrics, conversations] = await Promise.all([
        serverFetchJson<ConversationMetrics>(
          `/api/metrics?${dateQuery.toString()}`,
          "Не удалось загрузить метрики за день.",
        ),
        serverFetchJson<ConversationListOut>(
          `/api/conversations?${conversationQuery.toString()}`,
          "Не удалось загрузить обращения за день.",
        ),
      ]);
      const ticketCount = conversations.ok ? conversations.data.total : 0;
      const autoAnswerPercent = dailyMetrics.ok
        ? dailyMetrics.data.auto_answer_percent
        : 0;
      return {
        date,
        tickets: ticketCount,
        autoReplies: Math.round((ticketCount * autoAnswerPercent) / 100),
        escalations: dailyMetrics.ok ? dailyMetrics.data.escalation_count : 0,
      };
    }),
  ]);
  return { metrics, trends: dailyData };
}
