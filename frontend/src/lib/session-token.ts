import { createHmac, timingSafeEqual } from "node:crypto";
import type { UserSession } from "@/src/types/domain";
import { parseUserSession } from "@/src/lib/user-session";

/** Подпись HMAC-SHA256: payload.signature, оба в base64url. */
export function encodeSessionToken(user: UserSession, secret: string): string {
  const payload = Buffer.from(JSON.stringify(user), "utf8").toString(
    "base64url",
  );
  const signature = createHmac("sha256", secret)
    .update(payload)
    .digest("base64url");
  return `${payload}.${signature}`;
}

export function decodeSessionToken(
  token: string | undefined,
  secret: string,
): UserSession | null {
  if (!token) {
    return null;
  }

  const separator = token.lastIndexOf(".");
  if (separator <= 0) {
    return null;
  }

  const payload = token.slice(0, separator);
  const signature = token.slice(separator + 1);
  const expected = createHmac("sha256", secret)
    .update(payload)
    .digest("base64url");

  const actualBuf = Buffer.from(signature);
  const expectedBuf = Buffer.from(expected);
  if (
    actualBuf.length !== expectedBuf.length ||
    !timingSafeEqual(actualBuf, expectedBuf)
  ) {
    return null;
  }

  try {
    const raw = Buffer.from(payload, "base64url").toString("utf8");
    return parseUserSession(raw);
  } catch {
    return null;
  }
}
