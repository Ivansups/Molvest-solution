import { apiClient } from "@/src/api/client";
import { ApiServiceError, toServiceError } from "@/src/services/service-helpers";
import type {
  ChatRequest,
  ChatResponse,
  ConversationDetailOut,
  ConversationListOut,
  ConversationOut,
} from "@/src/types/api";
import type {
  ConversationDetail,
  ConversationListItem,
  ConversationMessage,
  ConversationPage,
} from "@/src/types/domain";

function toListItem(conversation: ConversationOut): ConversationListItem {
  return {
    id: conversation.id,
    userId: conversation.user_id,
    status: conversation.status,
    createdAt: conversation.created_at,
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
    lastMessageAt: conversation.messages.at(-1)?.created_at ?? conversation.created_at,
    priority: "medium",
    unread: 0,
    suggestedResponse: conversation.suggested_response ?? "",
    resolveComment: conversation.resolve_comment ?? null,
    resolveConfirmedAt: conversation.resolve_confirmed_at ?? null,
    userProfile: { company: "", department: "", position: "", lastSeenAt: "" },
    messages: conversation.messages.map(toMessage),
  };
}

export const chatService = {
  async listConversations(
    installationId: string,
    page: number,
    pageSize: number,
    status?: ConversationListItem["status"],
  ): Promise<ConversationPage> {
    try {
      const response = await apiClient.get<ConversationListOut>("/api/conversations", {
        params: {
          installation_id: installationId,
          page,
          page_size: pageSize,
          ...(status ? { status } : {}),
        },
      });
      return {
        items: response.data.items.map(toListItem),
        page: response.data.page,
        pageSize: response.data.page_size,
        total: response.data.total,
      };
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить список диалогов.",
        "/api/conversations",
      );
    }
  },

  async getConversation(
    ticketId: string,
    installationId: string,
  ): Promise<ConversationDetail | null> {
    try {
      const response = await apiClient.get<ConversationDetailOut>(
        `/api/conversations/${ticketId}`,
        {
          params: { installation_id: installationId },
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

  async sendOperatorReply(
    conversationId: string,
    installationId: string,
    text: string,
  ): Promise<void> {
    try {
      await apiClient.post(`/api/conversations/${conversationId}/messages`, {
        installation_id: installationId,
        text,
      });
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось отправить ответ оператора.",
        `/api/conversations/${conversationId}/messages`,
      );
    }
  },

  async resolveConversation(
    conversationId: string,
    installationId: string,
    comment?: string,
  ): Promise<void> {
    try {
      await apiClient.post(`/api/conversations/${conversationId}/resolve`, {
        installation_id: installationId,
        confirmed: true,
        ...(comment ? { comment } : {}),
      });
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось закрыть диалог.",
        `/api/conversations/${conversationId}/resolve`,
      );
    }
  },

  async generateSuggestion(
    conversationId: string,
    installationId: string,
  ): Promise<ConversationDetail> {
    try {
      const response = await apiClient.post<ConversationDetailOut>(
        `/api/conversations/${conversationId}/suggest`,
        { installation_id: installationId },
        { timeout: 60_000 },
      );
      return toDetail(response.data);
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось сгенерировать черновик.",
        `/api/conversations/${conversationId}/suggest`,
      );
    }
  },
};
