import { describe, expect, it } from "vitest";
import { getSupportInstallationId, resolveUserRole, toUserSession } from "@/src/lib/auth-user";

describe("auth user helpers", () => {
  it("derivesRoleFromEmailWhenStoredRoleMissing", () => {
    expect(resolveUserRole("operator@molvest.ru")).toBe("operator");
    expect(resolveUserRole("admin@molvest.ru")).toBe("admin");
  });

  it("buildsAppSessionFromNextAuthPayload", () => {
    const session = toUserSession({
      expires: "2099-01-01T00:00:00.000Z",
      user: {
        id: "user-01",
        email: "operator@molvest.ru",
        name: "Анна",
        role: "operator",
        installationId: "installation-01",
      },
    });

    expect(session).toEqual({
      id: "user-01",
      email: "operator@molvest.ru",
      name: "Анна",
      role: "operator",
      installationId: "installation-01",
    });
  });

  it("fallsBackToDefaultInstallationId", () => {
    const session = toUserSession({
      expires: "2099-01-01T00:00:00.000Z",
      user: {
        id: "user-02",
        email: "admin@molvest.ru",
        name: null,
        role: "admin",
      },
    });

    expect(session?.installationId).toBe(getSupportInstallationId());
  });
});
