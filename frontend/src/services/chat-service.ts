import { apiClient } from "@/src/api/client";
import {
  toServiceError,
  unsupportedEndpoint,
} from "@/src/services/service-helpers";
import type { ChatRequest, ChatResponse } from "@/src/types/api";
import type { ConversationDetail, ConversationPreview } from "@/src/types/domain";

export const chatService = {
  async listConversations(): Promise<ConversationPreview[]> {
    unsupportedEndpoint(
      "/api/conversations",
      "Бэкенд пока не публикует список диалогов для support-панели.",
    );
  },

  async getConversation(ticketId: string): Promise<ConversationDetail | null> {
    unsupportedEndpoint(
      `/api/conversations/${ticketId}`,
      "Бэкенд пока не публикует детали диалога для support-панели.",
    );
  },

  async sendMessage(
    request: ChatRequest,
  ): Promise<ChatResponse> {
    try {
      const response = await apiClient.post<ChatResponse>("/chat", request, {
        timeout: 60_000,
      });
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось получить ответ от backend /chat.",
        "/chat",
      );
    }
  },
};
