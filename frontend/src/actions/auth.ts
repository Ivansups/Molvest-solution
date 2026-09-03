"use server";

import { AuthError } from "next-auth";
import { cookies } from "next/headers";
import { signIn, signOut } from "@/auth";

const SESSION_COOKIE_SUFFIX = "authjs.session-token";

/**
 * Убирает срок жизни у куки сессии: браузер удалит её при закрытии.
 * Auth.js задаёт maxAge конфигом, поэтому «запомнить меня» решается здесь.
 */
async function makeSessionCookieEphemeral(): Promise<void> {
  const store = await cookies();
  const sessionCookie = store
    .getAll()
    .find((cookie) => cookie.name.endsWith(SESSION_COOKIE_SUFFIX));
  if (!sessionCookie) {
    return;
  }

  store.set(sessionCookie.name, sessionCookie.value, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: sessionCookie.name.startsWith("__Secure-"),
  });
}

export async function loginAction(
  email: string,
  password: string,
  remember: boolean,
): Promise<string> {
  try {
    const nextUrl = await signIn("credentials", {
      email,
      password,
      redirect: false,
      redirectTo: "/",
    });
    const url = new URL(nextUrl ?? "/", "http://localhost");
    const authError = url.searchParams.get("error");
    if (authError) {
      throw new Error("Проверьте email и пароль сотрудника.");
    }
    if (!remember) {
      await makeSessionCookieEphemeral();
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch (error) {
    if (error instanceof AuthError) {
      throw new Error("Проверьте email и пароль сотрудника.");
    }
    throw error;
  }
}

export async function logoutAction(): Promise<string> {
  await signOut({
    redirect: false,
    redirectTo: "/login",
  });
  return "/login";
}
