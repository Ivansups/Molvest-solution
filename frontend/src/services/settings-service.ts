import { apiClient } from "@/src/api/client";
import { toServiceError } from "@/src/services/service-helpers";
import type { SystemSettings } from "@/src/types/domain";

export const settingsService = {
  async getSettings(): Promise<SystemSettings> {
    try {
      const response = await apiClient.get<SystemSettings>("/api/settings");
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не публикует настройки системы.",
        "/api/settings",
      );
    }
  },

  async saveSettings(nextSettings: SystemSettings): Promise<SystemSettings> {
    try {
      const response = await apiClient.put<SystemSettings>("/api/settings", nextSettings);
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Бэкенд пока не принимает сохранение настроек.",
        "/api/settings",
      );
    }
  },
};
