/** Поколение локального гостевого сеанса: stale-запросы после reset. */

export const GUEST_CONVERSATION_KEY = "guest_conversation_id";
export const GUEST_HISTORY_KEY = "guest_conversation_history";
export const GUEST_HISTORY_LIMIT = 20;

/** Короткий текст кнопки «Позвать оператора» — не зависит от классификатора. */
export const GUEST_HANDOFF_TEXT = "Позовите оператора";

export type GuestHistoryStatus = "open" | "escalated" | "resolved";

/** Локальная строка «Мои обращения»: только id, которые браузер уже знает. */
export interface GuestHistoryItem {
  id: string;
  preview: string;
  status?: GuestHistoryStatus;
  updatedAt: string;
}

function canUseBrowserStorage(): boolean {
  return typeof window !== "undefined";
}

function isHistoryStatus(value: unknown): value is GuestHistoryStatus {
  return value === "open" || value === "escalated" || value === "resolved";
}

function parseHistoryItem(value: unknown): GuestHistoryItem | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  if (!("id" in value) || typeof value.id !== "string" || !value.id) {
    return null;
  }
  const preview =
    "preview" in value && typeof value.preview === "string" ? value.preview : "";
  const status =
    "status" in value && isHistoryStatus(value.status) ? value.status : undefined;
  const updatedAt =
    "updatedAt" in value && typeof value.updatedAt === "string" && value.updatedAt
      ? value.updatedAt
      : new Date().toISOString();
  return { id: value.id, preview, status, updatedAt };
}

function parseHistory(raw: string | null): GuestHistoryItem[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    const seen = new Set<string>();
    const items: GuestHistoryItem[] = [];
    for (const entry of parsed) {
      const item = parseHistoryItem(entry);
      if (item === null || seen.has(item.id)) {
        continue;
      }
      seen.add(item.id);
      items.push(item);
      if (items.length >= GUEST_HISTORY_LIMIT) {
        break;
      }
    }
    return items;
  } catch {
    return [];
  }
}

function writeGuestHistory(items: GuestHistoryItem[]): void {
  window.localStorage.setItem(GUEST_HISTORY_KEY, JSON.stringify(items));
}

/** sessionStorage, иначе localStorage; пустой session не перекрывает local. */
export function readGuestConversationId(): string | null {
  if (!canUseBrowserStorage()) {
    return null;
  }
  const sessionValue = window.sessionStorage.getItem(GUEST_CONVERSATION_KEY);
  if (sessionValue) {
    return sessionValue;
  }
  const localValue = window.localStorage.getItem(GUEST_CONVERSATION_KEY);
  if (localValue) {
    window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, localValue);
    return localValue;
  }
  return null;
}

export function readGuestHistory(): GuestHistoryItem[] {
  if (!canUseBrowserStorage()) {
    return [];
  }
  const items = parseHistory(window.localStorage.getItem(GUEST_HISTORY_KEY));
  const currentId = readGuestConversationId();
  if (!currentId || items.some((item) => item.id === currentId)) {
    return items;
  }
  const seeded = [
    {
      id: currentId,
      preview: "",
      updatedAt: new Date().toISOString(),
    },
    ...items,
  ].slice(0, GUEST_HISTORY_LIMIT);
  writeGuestHistory(seeded);
  return seeded;
}

export function rememberGuestConversation(
  item: GuestHistoryItem,
): GuestHistoryItem[] {
  if (!canUseBrowserStorage()) {
    return [];
  }
  const current = readGuestHistory();
  const previous = current.find((entry) => entry.id === item.id);
  const merged: GuestHistoryItem = {
    id: item.id,
    preview: item.preview || previous?.preview || "",
    status: item.status ?? previous?.status,
    updatedAt: item.updatedAt || previous?.updatedAt || new Date().toISOString(),
  };
  const next = [
    merged,
    ...current.filter((entry) => entry.id !== item.id),
  ].slice(0, GUEST_HISTORY_LIMIT);
  writeGuestHistory(next);
  return next;
}

export function forgetGuestConversation(conversationId: string): GuestHistoryItem[] {
  if (!canUseBrowserStorage()) {
    return [];
  }
  const next = readGuestHistory().filter((item) => item.id !== conversationId);
  writeGuestHistory(next);
  if (readGuestConversationId() === conversationId) {
    clearGuestConversationId();
  }
  return next;
}

export function writeGuestConversationId(conversationId: string): void {
  if (!canUseBrowserStorage()) {
    return;
  }
  window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, conversationId);
  window.localStorage.setItem(GUEST_CONVERSATION_KEY, conversationId);
  rememberGuestConversation({
    id: conversationId,
    preview: "",
    updatedAt: new Date().toISOString(),
  });
}

export function clearGuestConversationId(): void {
  if (!canUseBrowserStorage()) {
    return;
  }
  window.sessionStorage.removeItem(GUEST_CONVERSATION_KEY);
  window.localStorage.removeItem(GUEST_CONVERSATION_KEY);
}

/** Ответ относится к уже сброшенному гостевому сеансу. */
export function isStaleGuestGeneration(
  requestGeneration: number,
  currentGeneration: number,
): boolean {
  return requestGeneration !== currentGeneration;
}

/** Текущий гостевой сеанс ещё ждёт ответ на отправку. */
export function isActiveGuestSend(
  pendingGeneration: number | null,
  currentGeneration: number,
): boolean {
  return pendingGeneration === currentGeneration;
}
