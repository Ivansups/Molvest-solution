import { describe, expect, it } from "vitest";
import {
  decodeSessionToken,
  encodeSessionToken,
} from "@/src/lib/session-token";
import type { UserSession } from "@/src/types/domain";

const user: UserSession = {
  id: "user-01",
  name: "Анна",
  email: "operator@molvest.ru",
  role: "operator",
  installationId: "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11",
};

const secret = "test-session-secret";

describe("session token", () => {
  it("roundTripsASignedSession", () => {
    const token = encodeSessionToken(user, secret);
    expect(decodeSessionToken(token, secret)).toEqual(user);
  });

  it("rejectsATokenSignedWithAnotherSecret", () => {
    const token = encodeSessionToken(user, secret);
    expect(decodeSessionToken(token, "other-secret")).toBeNull();
  });

  it("rejectsATamperedPayload", () => {
    const token = encodeSessionToken(user, secret);
    const [payload, signature] = token.split(".");
    const tampered = Buffer.from(
      JSON.stringify({ ...user, role: "admin" }),
      "utf8",
    ).toString("base64url");
    expect(decodeSessionToken(`${tampered}.${signature}`, secret)).toBeNull();
    expect(payload).not.toBe(tampered);
  });

  it("returnsNullWhenTokenIsMissing", () => {
    expect(decodeSessionToken(undefined, secret)).toBeNull();
    expect(decodeSessionToken("", secret)).toBeNull();
    expect(decodeSessionToken("no-dot", secret)).toBeNull();
  });
});
