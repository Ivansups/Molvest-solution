import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";

export interface HealthResponse {
  status: string;
}

export const healthService = {
  async getHealth(): Promise<HealthResponse> {
    try {
      const response = await apiClient.get<HealthResponse>("/health");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось получить статус backend /health.",
        "/health",
      );
    }
  },
};
