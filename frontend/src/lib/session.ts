import { cache } from "react";
import { toUserSession } from "@/src/lib/auth-user";
import { isNextProductionBuild } from "@/src/lib/build-phase";
import type { UserSession } from "@/src/types/domain";

export const getSession = cache(async (): Promise<UserSession | null> => {
  // Публичные страницы должны собираться без auth-БД. В рантайме отсутствие
  // конфигурации — ошибка, а не «пользователь не залогинен».
  if (isNextProductionBuild()) {
    return null;
  }

  const { auth } = await import("@/auth");
  return toUserSession(await auth());
});
