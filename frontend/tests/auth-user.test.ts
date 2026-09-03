import { describe, expect, it } from "vitest";
import { getSupportInstallationId, resolveUserRole, toUserSession } from "@/src/lib/auth-user";

describe("auth user helpers", () => {
  it("acceptsOnlyKnownRoles", () => {
    expect(resolveUserRole("operator")).toBe("operator");
    expect(resolveUserRole("admin")).toBe("admin");
  });

  it("deniesUnknownOrMissingRole", () => {
    expect(resolveUserRole(null)).toBeNull();
    expect(resolveUserRole(undefined)).toBeNull();
    expect(resolveUserRole("")).toBeNull();
    expect(resolveUserRole("support")).toBeNull();
  });

  it("rejectsSessionWithoutRole", () => {
    const session = toUserSession({
      expires: "2099-01-01T00:00:00.000Z",
      user: {
        id: "user-03",
        email: "someone@molvest.ru",
        name: null,
      },
    });

    expect(session).toBeNull();
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
