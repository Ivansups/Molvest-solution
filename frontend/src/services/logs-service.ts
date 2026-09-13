import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { LogEventListOut, LogEventType } from "@/src/types/api";

function toUtcStart(date: string): string {
  return `${date}T00:00:00.000Z`;
}

function toUtcEnd(date: string): string {
  return `${date}T23:59:59.999Z`;
}

export const logsService = {
  async listEvents(params: {
    installationId: string;
    eventType?: LogEventType | "all";
    dateFrom?: string;
    dateTo?: string;
    page?: number;
    pageSize?: number;
  }): Promise<LogEventListOut> {
    try {
      const response = await apiClient.get<LogEventListOut>("/api/logs", {
        params: {
          installation_id: params.installationId,
          event_type:
            !params.eventType || params.eventType === "all"
              ? undefined
              : params.eventType,
          date_from: params.dateFrom ? toUtcStart(params.dateFrom) : undefined,
          date_to: params.dateTo ? toUtcEnd(params.dateTo) : undefined,
          page: params.page ?? 1,
          page_size: params.pageSize ?? 50,
        },
      });
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить журнал событий.",
        "/api/logs",
      );
    }
  },
};
