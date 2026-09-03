import { apiClient } from "@/src/api/client";
import { ApiServiceError, toServiceError } from "@/src/services/service-helpers";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import type {
  ChatRequest,
  ChatResponse,
  ConversationDetailOut,
  ConversationOut,
} from "@/src/types/api";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationPreview,
} from "@/src/types/domain";

function toPreview(conversation: ConversationOut): ConversationPreview {
  return {
    id: conversation.id,
    subject: conversation.user_id,
    userId: conversation.user_id,
    userName: conversation.user_id,
    channel: "Bitrix24",
    status: conversation.status,
    lastMessage: "",
    lastMessageAt: conversation.created_at,
    priority: "medium",
    unread: 0,
    suggestedResponse: "",
  };
}

function toMessage(message: ConversationDetailOut["messages"][number]): ConversationMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    confidence: message.confidence ?? undefined,
    escalated: message.escalated,
    sources: message.sources,
  };
}

function toDetail(conversation: ConversationDetailOut): ConversationDetail {
  return {
    id: conversation.id,
    subject: conversation.user_id,
    userId: conversation.user_id,
    userName: conversation.user_id,
    channel: "Bitrix24",
    status: conversation.status,
    lastMessage: conversation.messages.at(-1)?.content ?? "",
    lastMessageAt: conversation.created_at,
    priority: "medium",
    unread: 0,
    suggestedResponse: "",
    userProfile: { company: "", department: "", position: "", lastSeenAt: "" },
    messages: conversation.messages.map(toMessage),
  };
}

export const chatService = {
  async listConversations(): Promise<ConversationPreview[]> {
    try {
      const response = await apiClient.get<{ items: ConversationOut[] }>(
        "/api/conversations",
        {
          params: { installation_id: DEFAULT_INSTALLATION_ID },
        },
      );
      return response.data.items.map(toPreview);
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить список диалогов.",
        "/api/conversations",
      );
    }
  },

  async getConversation(ticketId: string): Promise<ConversationDetail | null> {
    try {
      const response = await apiClient.get<ConversationDetailOut>(
        `/api/conversations/${ticketId}`,
        {
          params: { installation_id: DEFAULT_INSTALLATION_ID },
        },
      );
      return toDetail(response.data);
    } catch (error) {
      // Не найден диалог в этой установке — штатный случай, а не ошибка запроса.
      if (error instanceof ApiServiceError && error.status === 404) {
        return null;
      }
      throw toServiceError(
        error,
        "Не удалось загрузить детали диалога.",
        `/api/conversations/${ticketId}`,
      );
    }
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
