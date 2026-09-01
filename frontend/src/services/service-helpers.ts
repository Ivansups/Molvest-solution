import axios from "axios";
import { getClientSession } from "@/src/lib/client-session";

export class ApiServiceError extends Error {
  status?: number;

  endpoint?: string;

  constructor(message: string, options?: { status?: number; endpoint?: string }) {
    super(message);
    this.name = "ApiServiceError";
    this.status = options?.status;
    this.endpoint = options?.endpoint;
  }
}

export function toServiceError(
  error: unknown,
  fallbackMessage: string,
  endpoint?: string,
): ApiServiceError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data;
    const responseMessage =
      typeof detail === "string"
        ? detail
        : typeof detail?.detail === "string"
          ? detail.detail
          : undefined;

    return new ApiServiceError(responseMessage ?? fallbackMessage, {
      status,
      endpoint,
    });
  }

  if (error instanceof Error) {
    return new ApiServiceError(error.message, { endpoint });
  }

  return new ApiServiceError(fallbackMessage, { endpoint });
}

export function unsupportedEndpoint(endpoint: string, message: string): never {
  throw new ApiServiceError(message, { status: 404, endpoint });
}

export function getStoredInstallationId(): string {
  const user = getClientSession();
  if (!user) {
    throw new ApiServiceError("Сначала выполните вход в панель поддержки.");
  }

  return user.installationId;
}

export async function delay<T>(value: T, timeout = 200): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, timeout));
  return value;
}
