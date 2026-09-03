import { cache } from "react";
import { auth } from "@/auth";
import { toUserSession } from "@/src/lib/auth-user";
import type { UserSession } from "@/src/types/domain";

export const getSession = cache(async (): Promise<UserSession | null> => {
  return toUserSession(await auth());
});
