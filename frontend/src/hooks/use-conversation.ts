"use client";

import { useState } from "react";

const GUEST_CONVERSATION_KEY = "guest_conversation_id";

/** Сохраняет идентификатор гостевого диалога до закрытия вкладки браузера. */
export function useConversation(): {
  conversationId: string | null;
  setConversationId: (conversationId: string) => void;
} {
  const [conversationId, setConversationIdState] = useState<string | null>(
    () =>
      typeof window === "undefined"
        ? null
        : window.sessionStorage.getItem(GUEST_CONVERSATION_KEY),
  );

  const setConversationId = (nextConversationId: string): void => {
    window.sessionStorage.setItem(GUEST_CONVERSATION_KEY, nextConversationId);
    setConversationIdState(nextConversationId);
  };

  return { conversationId, setConversationId };
}
