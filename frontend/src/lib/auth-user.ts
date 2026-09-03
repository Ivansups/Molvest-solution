import type { Session } from "next-auth";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import type { AppRole, UserSession } from "@/src/types/domain";

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

/** Роль только из явного значения: неизвестное значение — отказ, не админ. */
export function resolveUserRole(storedRole?: string | null): AppRole | null {
  return isAppRole(storedRole) ? storedRole : null;
}

export function displayNameForRole(role: AppRole): string {
  return role === "operator" ? "Анна Лебедева" : "Екатерина Романова";
}

export function getSupportInstallationId(): string {
  const configured = process.env.SUPPORT_INSTALLATION_ID?.trim();
  return configured || DEFAULT_INSTALLATION_ID;
}

export function toUserSession(session: Session | null): UserSession | null {
  const user = session?.user;
  if (!user?.id || !user.email) {
    return null;
  }

  const role = resolveUserRole(user.role);
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
