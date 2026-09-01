import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { DashboardData } from "@/src/types/domain";

export const dashboardService = {
  async getDashboard(): Promise<DashboardData> {
    try {
      const response = await apiClient.get<DashboardData>("/api/dashboard");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не публикует данные дашборда.",
        "/api/dashboard",
      );
    }
  },
};
