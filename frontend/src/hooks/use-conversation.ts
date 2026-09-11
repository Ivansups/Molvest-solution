"use client";

import { useCallback, useState } from "react";
import {
  clearGuestConversationId,
  forgetGuestConversation,
  readGuestConversationId,
  readGuestHistory,
  rememberGuestConversation,
  writeGuestConversationId,
  type GuestHistoryItem,
} from "@/src/lib/guest-session";

/** Текущий гостевой диалог и локальная история id с этого браузера. */
export function useConversation(): {
  conversationId: string | null;
  history: GuestHistoryItem[];
  setConversationId: (conversationId: string) => void;
  resetConversation: () => void;
  rememberConversation: (item: GuestHistoryItem) => void;
  forgetConversation: (conversationId: string) => void;
} {
  const [conversationId, setConversationIdState] = useState<string | null>(
    () => readGuestConversationId(),
  );
  const [history, setHistory] = useState<GuestHistoryItem[]>(() =>
    readGuestHistory(),
  );

  const setConversationId = (nextConversationId: string): void => {
    writeGuestConversationId(nextConversationId);
    setConversationIdState(nextConversationId);
    setHistory(readGuestHistory());
  };

  const resetConversation = (): void => {
    if (conversationId) {
      rememberGuestConversation({
        id: conversationId,
        preview: "",
        updatedAt: new Date().toISOString(),
      });
    }
    clearGuestConversationId();
    setConversationIdState(null);
    setHistory(readGuestHistory());
  };

  const rememberConversation = useCallback((item: GuestHistoryItem): void => {
    setHistory(rememberGuestConversation(item));
  }, []);

  const forgetConversation = useCallback((id: string): void => {
    const next = forgetGuestConversation(id);
    setHistory(next);
    setConversationIdState((current) => (current === id ? null : current));
  }, []);

  return {
    conversationId,
    history,
    setConversationId,
    resetConversation,
    rememberConversation,
    forgetConversation,
  };
}
