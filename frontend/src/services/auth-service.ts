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
      installationId: "7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11",
    });
  },
};

