import { describe, expect, it } from "vitest";
import {
  isActiveGuestSend,
  isStaleGuestGeneration,
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
