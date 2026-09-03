import { describe, expect, it } from "vitest";
import {
  decodeSessionToken,
  encodeSessionToken,
} from "@/src/lib/session-token";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import type { UserSession } from "@/src/types/domain";

const user: UserSession = {
  id: "user-01",
  name: "Анна",
  email: "operator@molvest.ru",
  role: "operator",
  installationId: DEFAULT_INSTALLATION_ID,
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
