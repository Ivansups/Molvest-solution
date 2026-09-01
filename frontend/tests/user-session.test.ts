import { describe, expect, it } from "vitest";
import { parseUserSession } from "@/src/lib/user-session";

const valid = {
  id: "user-01",
  name: "Анна",
  email: "operator@molvest.ru",
  role: "operator" as const,
  installationId: "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11",
};

describe("parseUserSession", () => {
  it("returnsNullWhenRawIsUndefined", () => {
    expect(parseUserSession(undefined)).toBeNull();
  });

  it("returnsNullWhenRawIsEmptyString", () => {
    expect(parseUserSession("")).toBeNull();
  });

  it("returnsNullOnInvalidJson", () => {
    expect(parseUserSession("{not-json")).toBeNull();
  });

  it("returnsNullWhenIdMissing", () => {
    expect(
      parseUserSession(JSON.stringify({ ...valid, id: "" })),
    ).toBeNull();
  });

  it("returnsNullWhenRoleMissing", () => {
    expect(
      parseUserSession(JSON.stringify({ ...valid, role: "" })),
    ).toBeNull();
  });

  it("returnsNullWhenRoleIsUnknown", () => {
    expect(
      parseUserSession(JSON.stringify({ ...valid, role: "adminx" })),
    ).toBeNull();
  });

  it("returnsNullWhenInstallationIdMissing", () => {
    expect(
      parseUserSession(JSON.stringify({ ...valid, installationId: "" })),
    ).toBeNull();
  });

  it("returnsSessionWhenRequiredFieldsPresent", () => {
    expect(parseUserSession(JSON.stringify(valid))).toEqual(valid);
  });
});
