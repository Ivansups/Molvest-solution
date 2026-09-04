import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();
vi.mock("@/src/lib/session", () => ({ getSession }));

const { DELETE, GET, POST } = await import("@/app/backend/[...path]/route");

const upstream = vi.fn<typeof fetch>(async () => new Response("ok", { status: 200 }));

function params(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

beforeEach(() => {
  vi.stubGlobal("fetch", upstream);
  getSession.mockResolvedValue(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("backend proxy", () => {
  it("rejectsAnonymousAdminRequests", async () => {
    const response = await DELETE(
      new Request("http://localhost/backend/api/documents/1", { method: "DELETE" }),
      params("api", "documents", "1"),
    );

    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("rejectsAnonymousConversationList", async () => {
    const response = await GET(
      new Request("http://localhost/backend/api/conversations"),
      params("api", "conversations"),
    );

    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("rejectsAnonymousOperatorSuggest", async () => {
    const response = await POST(
      new Request("http://localhost/backend/api/conversations/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/suggest", {
        method: "POST",
        body: "{}",
      }),
      params("api", "conversations", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "suggest"),
    );

    expect(response.status).toBe(401);
    expect(upstream).not.toHaveBeenCalled();
  });

  it("allowsAnonymousGuestConversationPollWithoutDraft", async () => {
    upstream.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          suggested_response: "секретный черновик",
          messages: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const response = await GET(
      new Request(
        "http://localhost/backend/api/conversations/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa?installation_id=7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11",
      ),
      params("api", "conversations", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    );

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledOnce();
    const body = (await response.json()) as { suggested_response?: string };
    expect(body.suggested_response).toBeUndefined();
  });

  it("keepsDraftForStaffConversationPoll", async () => {
    getSession.mockResolvedValue({ user: { id: "op-1" } });
    upstream.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          suggested_response: "черновик оператора",
          messages: [],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const response = await GET(
      new Request(
        "http://localhost/backend/api/conversations/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      ),
      params("api", "conversations", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    );

    expect(response.status).toBe(200);
    const body = (await response.json()) as { suggested_response?: string };
    expect(body.suggested_response).toBe("черновик оператора");
  });

  it("allowsAnonymousGuestChat", async () => {
    const response = await POST(
      new Request("http://localhost/backend/chat", { method: "POST", body: "{}" }),
      params("chat"),
    );

    expect(response.status).toBe(200);
    expect(upstream).toHaveBeenCalledOnce();
  });

  it("dropsClientSuppliedInternalToken", async () => {
    await POST(
      new Request("http://localhost/backend/chat", {
        method: "POST",
        body: "{}",
        headers: { "X-Internal-Token": "forged" },
      }),
      params("chat"),
    );

    const init = upstream.mock.calls[0][1];
    expect(new Headers(init?.headers).get("x-internal-token")).toBeNull();
  });
});
