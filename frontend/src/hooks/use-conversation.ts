"use client";

import { useCallback, useState } from "react";
import {
  clearGuestConversationId,
  forgetGuestConversation,
  readGuestConversationId,
  writeGuestConversationId,
} from "@/src/lib/guest-session";

/** Текущий гостевой диалог: id, сохранённый в этом браузере. */
export function useConversation(): {
  conversationId: string | null;
  setConversationId: (conversationId: string) => void;
  resetConversation: () => void;
  forgetConversation: (conversationId: string) => void;
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

  const forgetConversation = useCallback((id: string): void => {
    forgetGuestConversation(id);
    setConversationIdState((current) => (current === id ? null : current));
  }, []);

  return {
    conversationId,
    setConversationId,
    resetConversation,
    forgetConversation,
  };
}
