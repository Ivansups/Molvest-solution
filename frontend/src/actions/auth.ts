"use server";

import { redirect } from "next/navigation";
import { clearSession, setSession } from "@/src/lib/session";
import { authService } from "@/src/services/auth-service";

export async function loginAction(
  email: string,
  password: string,
  remember: boolean,
): Promise<void> {
  const user = await authService.login(email, password);
  await setSession(user, { remember });
}

export async function logoutAction(): Promise<void> {
  await clearSession();
  redirect("/login");
}
