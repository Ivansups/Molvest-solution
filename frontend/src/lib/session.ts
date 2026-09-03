import { cache } from "react";
import { toUserSession } from "@/src/lib/auth-user";
import type { UserSession } from "@/src/types/domain";

function hasAuthDatabaseConfig(): boolean {
  return Boolean(
    process.env.AUTH_DATABASE_URL?.trim() ||
      process.env.DATABASE_URL?.trim(),
  );
}

export const getSession = cache(async (): Promise<UserSession | null> => {
  // Публичные страницы должны собираться даже без auth-БД в окружении build.
  if (!hasAuthDatabaseConfig()) {
    return null;
  }

  const { auth } = await import("@/auth");
  return toUserSession(await auth());
});
