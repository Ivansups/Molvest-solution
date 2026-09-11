"use client";

import { useState } from "react";
import {
  clearGuestConversationId,
  readGuestConversationId,
  writeGuestConversationId,
} from "@/src/lib/guest-session";

/** Сохраняет id гостевого диалога в sessionStorage и localStorage. */
export function useConversation(): {
  conversationId: string | null;
  setConversationId: (conversationId: string) => void;
  resetConversation: () => void;
} {
  const [conversationId, setConversationIdState] = useState<string | null>(
    () => readGuestConversationId(),
  );

  const setConversationId = (nextConversationId: string): void => {
    writeGuestConversationId(nextConversationId);
    setConversationIdState(nextConversationId);
  };

  const resetConversation = (): void => {
    clearGuestConversationId();
    setConversationIdState(null);
  };

  return { conversationId, setConversationId, resetConversation };
}
