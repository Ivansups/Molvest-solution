import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { ConversationMetrics } from "@/src/types/api";

export const analyticsService = {
  async getMetrics(params: {
    installationId: string;
    dateFrom?: string;
    dateTo?: string;
  }): Promise<ConversationMetrics> {
    try {
      const response = await apiClient.get<ConversationMetrics>("/api/metrics", {
        params: {
          installation_id: params.installationId,
          date_from: params.dateFrom || undefined,
          date_to: params.dateTo || undefined,
        },
      });
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить метрики диалогов.",
        "/api/metrics",
      );
    }
  },
};
