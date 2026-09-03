import { describe, expect, it } from "vitest";
import {
  getClientSession,
  setClientSession,
} from "@/src/lib/client-session";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import { getStoredInstallationId } from "@/src/services/service-helpers";
import type { UserSession } from "@/src/types/domain";

const user: UserSession = {
  id: "user-01",
  name: "Анна",
  email: "operator@molvest.ru",
  role: "operator",
  installationId: DEFAULT_INSTALLATION_ID,
};

describe("getStoredInstallationId", () => {
  it("throwsWhenClientSessionIsEmpty", () => {
    setClientSession(null);
    expect(() => getStoredInstallationId()).toThrow(
      "Сначала выполните вход в панель поддержки.",
    );
  });

  it("returnsInstallationIdFromClientSession", () => {
    setClientSession(user);
    expect(getStoredInstallationId()).toBe(user.installationId);
    expect(getClientSession()).toEqual(user);
    setClientSession(null);
  });
});
