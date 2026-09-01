import type { AppRole, UserSession } from "@/src/types/domain";

export const SESSION_COOKIE = "molvest-user";

function isAppRole(value: unknown): value is AppRole {
  return value === "admin" || value === "operator";
}

export function parseUserSession(raw: string | undefined): UserSession | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    const obj = parsed as Record<string, unknown>;
    if (
      typeof obj.id !== "string" ||
      obj.id.length === 0 ||
      typeof obj.name !== "string" ||
      typeof obj.email !== "string" ||
      typeof obj.installationId !== "string" ||
      obj.installationId.length === 0 ||
      !isAppRole(obj.role)
    ) {
      return null;
    }

    return {
      id: obj.id,
      name: obj.name,
      email: obj.email,
      role: obj.role,
      installationId: obj.installationId,
    };
  } catch {
    return null;
  }
}
