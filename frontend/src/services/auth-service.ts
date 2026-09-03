import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import { delay } from "@/src/services/service-helpers";
import type { UserSession } from "@/src/types/domain";

export const authService = {
  async login(email: string, password: string): Promise<UserSession> {
    if (!email || !password) {
      throw new Error("Неверные учётные данные");
    }

    const role = email.includes("operator") ? "operator" : "admin";
    return delay({
      id: "user-01",
      name: role === "operator" ? "Анна Лебедева" : "Екатерина Романова",
      email,
      role,
      installationId: DEFAULT_INSTALLATION_ID,
    });
  },
};

