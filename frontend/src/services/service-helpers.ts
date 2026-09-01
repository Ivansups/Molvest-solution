import axios from "axios";

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
  if (typeof window === "undefined") {
    throw new ApiServiceError("Не удалось определить installation_id текущего пользователя.");
  }

  const raw = window.localStorage.getItem("molvest-user");
  if (!raw) {
    throw new ApiServiceError("Сначала выполните вход в панель поддержки.");
  }

  const parsed = JSON.parse(raw) as { installationId?: string };
  if (!parsed.installationId) {
    throw new ApiServiceError("В сессии отсутствует installation_id.");
  }

  return parsed.installationId;
}

export async function delay<T>(value: T, timeout = 200): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, timeout));
  return value;
}
