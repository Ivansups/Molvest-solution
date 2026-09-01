import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { ActiveTicket, AnalyticsData, AuditLogItem } from "@/src/types/domain";

export const analyticsService = {
  async getAnalytics(): Promise<AnalyticsData> {
    try {
      const response = await apiClient.get<AnalyticsData>("/api/analytics");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не публикует аналитические метрики.",
        "/api/analytics",
      );
    }
  },

  async getLogs(): Promise<AuditLogItem[]> {
    try {
      const response = await apiClient.get<AuditLogItem[]>("/api/logs");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не публикует журнал логов.",
        "/api/logs",
      );
    }
  },

  async getActiveTickets(): Promise<ActiveTicket[]> {
    try {
      const response = await apiClient.get<ActiveTicket[]>("/api/operator/tickets");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не публикует активные операторские тикеты.",
        "/api/operator/tickets",
      );
    }
  },
};
