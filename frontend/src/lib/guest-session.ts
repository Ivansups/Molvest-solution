/** Поколение локального гостевого сеанса: stale-запросы после reset. */

export const GUEST_CONVERSATION_KEY = "guest_conversation_id";

/** Короткий текст кнопки «Позвать оператора» — не зависит от классификатора. */
export const GUEST_HANDOFF_TEXT = "Позовите оператора";

function canUseBrowserStorage(): boolean {
  return typeof window !== "undefined";
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

export function writeGuestConversationId(conversationId: string): void {
  if (!canUseBrowserStorage()) {
    return;
  }
  window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, conversationId);
  window.localStorage.setItem(GUEST_CONVERSATION_KEY, conversationId);
}

export function clearGuestConversationId(): void {
  if (!canUseBrowserStorage()) {
    return;
  }
  window.sessionStorage.removeItem(GUEST_CONVERSATION_KEY);
  window.localStorage.removeItem(GUEST_CONVERSATION_KEY);
}

/** Гостевой конверсейшн-id сброшен: сигнал сбросить локальный кэш, если он совпадает. */
export function forgetGuestConversation(conversationId: string): void {
  if (readGuestConversationId() === conversationId) {
    clearGuestConversationId();
  }
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
