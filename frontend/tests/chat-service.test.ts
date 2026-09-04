import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/src/api/client", () => ({
  apiClient: { get, post },
}));

const { chatService } = await import("@/src/services/chat-service");

const detail = {
  id: "c1",
  installation_id: "i1",
  user_id: "guest",
  status: "escalated" as const,
  created_at: "2026-01-01T00:00:00.000Z",
  suggested_response: "черновик",
  messages: [],
  escalations: [],
};

beforeEach(() => {
  get.mockReset();
  post.mockReset();
});

describe("chatService operator actions", () => {
  it("never posts operator actions to /chat", async () => {
    post.mockResolvedValue({ data: detail });
    await chatService.sendOperatorReply("c1", "i1", "ответ");
    await chatService.resolveConversation("c1", "i1");
    await chatService.generateSuggestion("c1", "i1");
    expect(post.mock.calls.map((call) => call[0])).toEqual([
      "/api/conversations/c1/messages",
      "/api/conversations/c1/resolve",
      "/api/conversations/c1/suggest",
    ]);
  });

  it("lists only escalated conversations when status is passed", async () => {
    get.mockResolvedValue({
      data: { items: [], page: 1, page_size: 50, total: 0 },
    });
    await chatService.listConversations("i1", 1, 50, "escalated");
    expect(get).toHaveBeenCalledWith("/api/conversations", {
      params: {
        installation_id: "i1",
        page: 1,
        page_size: 50,
        status: "escalated",
      },
    });
  });
});
