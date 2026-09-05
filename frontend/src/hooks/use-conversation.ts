"use client";

import { useCallback, useSyncExternalStore } from "react";

const GUEST_CONVERSATION_KEY = "guest_conversation_id";
const GUEST_CONVERSATION_EVENT = "guest-conversation-change";

function subscribe(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(GUEST_CONVERSATION_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(GUEST_CONVERSATION_EVENT, onStoreChange);
  };
}

function getConversationId(): string | null {
  return window.sessionStorage.getItem(GUEST_CONVERSATION_KEY);
}

function getServerConversationId(): null {
  return null;
}

/** Сохраняет идентификатор гостевого диалога до закрытия вкладки браузера. */
export function useConversation(): {
  conversationId: string | null;
  setConversationId: (conversationId: string) => void;
} {
  const conversationId = useSyncExternalStore(
    subscribe,
    getConversationId,
    getServerConversationId,
  );

  const setConversationId = useCallback((nextConversationId: string) => {
    window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, nextConversationId);
    window.dispatchEvent(new Event(GUEST_CONVERSATION_EVENT));
  }, []);

  return { conversationId, setConversationId };
}
