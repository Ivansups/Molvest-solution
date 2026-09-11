import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearGuestConversationId,
  GUEST_CONVERSATION_KEY,
  isActiveGuestSend,
  isStaleGuestGeneration,
  readGuestConversationId,
  writeGuestConversationId,
} from "@/src/lib/guest-session";

describe("guest session generation", () => {
  it("treats a reset generation as stale", () => {
    expect(isStaleGuestGeneration(0, 1)).toBe(true);
    expect(isStaleGuestGeneration(1, 1)).toBe(false);
  });

  it("hides the pending send after reset", () => {
    expect(isActiveGuestSend(0, 0)).toBe(true);
    expect(isActiveGuestSend(null, 1)).toBe(false);
    expect(isActiveGuestSend(0, 1)).toBe(false);
  });

  it("keeps the new send pending after a previous request is ignored", () => {
    expect(isActiveGuestSend(1, 1)).toBe(true);
  });
});

describe("guest conversation storage", () => {
  const store = (initial: Record<string, string> = {}) => {
    const data = { ...initial };
    return {
      getItem: (key: string) => data[key] ?? null,
      setItem: (key: string, value: string) => {
        data[key] = value;
      },
      removeItem: (key: string) => {
        delete data[key];
      },
      clear: () => {
        for (const key of Object.keys(data)) {
          delete data[key];
        }
      },
    };
  };

  beforeEach(() => {
    vi.stubGlobal("window", {
      sessionStorage: store(),
      localStorage: store(),
    });
  });

  it("reads sessionStorage before localStorage", () => {
    window.localStorage.setItem(GUEST_CONVERSATION_KEY, "from-local");
    window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, "from-session");
    expect(readGuestConversationId()).toBe("from-session");
  });

  it("falls back to localStorage and copies it into the session", () => {
    window.localStorage.setItem(GUEST_CONVERSATION_KEY, "from-local");
    expect(readGuestConversationId()).toBe("from-local");
    expect(window.sessionStorage.getItem(GUEST_CONVERSATION_KEY)).toBe(
      "from-local",
    );
  });

  it("writes the id to both stores", () => {
    writeGuestConversationId("abc");
    expect(window.sessionStorage.getItem(GUEST_CONVERSATION_KEY)).toBe("abc");
    expect(window.localStorage.getItem(GUEST_CONVERSATION_KEY)).toBe("abc");
  });

  it("clears both stores on new conversation", () => {
    writeGuestConversationId("abc");
    clearGuestConversationId();
    expect(window.sessionStorage.getItem(GUEST_CONVERSATION_KEY)).toBeNull();
    expect(window.localStorage.getItem(GUEST_CONVERSATION_KEY)).toBeNull();
    expect(readGuestConversationId()).toBeNull();
  });
});

describe("guest session generation", () => {
  it("treats a reset generation as stale", () => {
    expect(isStaleGuestGeneration(0, 1)).toBe(true);
    expect(isStaleGuestGeneration(1, 1)).toBe(false);
  });

  it("hides the pending send after reset", () => {
    expect(isActiveGuestSend(0, 0)).toBe(true);
    expect(isActiveGuestSend(null, 1)).toBe(false);
    expect(isActiveGuestSend(0, 1)).toBe(false);
  });

  it("keeps the new send pending after a previous request is ignored", () => {
    expect(isActiveGuestSend(1, 1)).toBe(true);
  });
});
