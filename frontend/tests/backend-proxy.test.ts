import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getSession = vi.fn();
vi.mock("@/src/lib/session", () => ({ getSession }));

const { DELETE, POST } = await import("@/app/backend/[...path]/route");

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
