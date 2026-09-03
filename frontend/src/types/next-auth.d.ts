import type { DefaultSession } from "next-auth";
import type { AppRole } from "@/src/types/domain";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      role?: AppRole;
      installationId?: string;
    } & DefaultSession["user"];
  }

  interface User {
    id: string;
    role?: AppRole;
    installationId?: string;
  }
}
