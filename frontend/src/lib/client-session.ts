import type { UserSession } from "@/src/types/domain";

let currentUser: UserSession | null = null;

/** Сессия с сервера: cookie httpOnly, клиент читает только этот снимок. */
export function setClientSession(user: UserSession | null): void {
  currentUser = user;
}

export function getClientSession(): UserSession | null {
  return currentUser;
}
