"use server";

import { AuthError } from "next-auth";
import { signIn, signOut } from "@/auth";

export async function loginAction(
  email: string,
  password: string,
  remember: boolean,
): Promise<string> {
  void remember;

  try {
    const nextUrl = await signIn("credentials", {
      email,
      password,
      redirect: false,
      redirectTo: "/",
    });
    const url = new URL(String(nextUrl), "http://localhost");
    const authError = url.searchParams.get("error");
    if (authError) {
      throw new Error("Проверьте email и пароль сотрудника.");
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
