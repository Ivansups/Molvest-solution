import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { AgentSettings } from "@/src/types/api";

export const settingsService = {
  async getSettings(): Promise<AgentSettings> {
    try {
      const response = await apiClient.get<AgentSettings>("/api/settings");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить настройки агента.",
        "/api/settings",
      );
    }
  },

  async saveSettings(nextSettings: AgentSettings): Promise<AgentSettings> {
    try {
      const response = await apiClient.put<AgentSettings>(
        "/api/settings",
        nextSettings,
      );
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось сохранить настройки агента.",
        "/api/settings",
      );
    }
  },
};
