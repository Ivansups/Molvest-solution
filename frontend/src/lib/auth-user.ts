import type { Session } from "next-auth";
import type { AppRole, UserSession } from "@/src/types/domain";

const DEFAULT_SUPPORT_INSTALLATION_ID =
  "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11";

export const DEMO_USERS = [
  {
    email: "admin@molvest.ru",
    name: "Екатерина Романова",
    role: "admin" as const,
  },
  {
    email: "operator@molvest.ru",
    name: "Анна Лебедева",
    role: "operator" as const,
  },
];

export function isAppRole(value: unknown): value is AppRole {
  return value === "admin" || value === "operator";
}

export function resolveUserRole(
  email: string,
  storedRole?: string | null,
): AppRole | null {
  if (isAppRole(storedRole)) {
    return storedRole;
  }

  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail) {
    return null;
  }

  return normalizedEmail.includes("operator") ? "operator" : "admin";
}

export function displayNameForRole(role: AppRole): string {
  return role === "operator" ? "Анна Лебедева" : "Екатерина Романова";
}

export function getSupportInstallationId(): string {
  const configured = process.env.SUPPORT_INSTALLATION_ID?.trim();
  return configured || DEFAULT_SUPPORT_INSTALLATION_ID;
}

export function toUserSession(session: Session | null): UserSession | null {
  const user = session?.user;
  if (!user?.id || !user.email) {
    return null;
  }

  const role = resolveUserRole(user.email, user.role);
  if (!role) {
    return null;
  }

  return {
    id: user.id,
    name: user.name ?? displayNameForRole(role),
    email: user.email,
    role,
    installationId: user.installationId ?? getSupportInstallationId(),
  };
}
