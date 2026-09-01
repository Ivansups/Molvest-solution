import { cache } from "react";
import { cookies } from "next/headers";
import type { UserSession } from "@/src/types/domain";
import { SESSION_COOKIE } from "@/src/lib/user-session";
import {
  decodeSessionToken,
  encodeSessionToken,
} from "@/src/lib/session-token";

export { SESSION_COOKIE };

const REMEMBER_MAX_AGE_SEC = 60 * 60 * 24 * 30;

function sessionSecret(): string {
  const secret = process.env.SESSION_SECRET || process.env.NEXTAUTH_SECRET;
  if (secret) {
    return secret;
  }
  if (process.env.NODE_ENV === "production") {
    throw new Error("SESSION_SECRET is not set");
  }
  return "dev-only-session-secret";
}

function cookieBase() {
  return {
    path: "/",
    sameSite: "lax" as const,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
  };
}

export const getSession = cache(async (): Promise<UserSession | null> => {
  const store = await cookies();
  return decodeSessionToken(store.get(SESSION_COOKIE)?.value, sessionSecret());
});

export async function setSession(
  user: UserSession,
  options?: { remember?: boolean },
): Promise<void> {
  const store = await cookies();
  const remember = options?.remember ?? true;
  store.set(SESSION_COOKIE, encodeSessionToken(user, sessionSecret()), {
    ...cookieBase(),
    ...(remember ? { maxAge: REMEMBER_MAX_AGE_SEC } : {}),
  });
}

export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.set(SESSION_COOKIE, "", {
    ...cookieBase(),
    maxAge: 0,
  });
}
