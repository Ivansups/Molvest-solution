"use client";

import { useState } from "react";
import { MessageBubble } from "@/src/components/common/message-bubble";
import { Spinner } from "@/src/components/ui/spinner";
import { cn } from "@/src/lib/utils";
import type { ConversationMessage } from "@/src/types/domain";

const THREAD_ENTER_STAGGER_MS = 48;
const THREAD_ENTER_STAGGER_MAX = 5;

function enterFromForRole(
  role: ConversationMessage["role"],
): "left" | "right" {
  // Гость слева; оператор, агент и система — справа, одной нитью.
  return role === "user" ? "left" : "right";
}

/** Лента сообщений: скелетон при загрузке и влёт пузырей при смене диалога. */
export function ConversationThread({
  conversationId,
  messages,
  isLoading,
  hideConfidence = false,
}: {
  conversationId: string | null;
  messages: ConversationMessage[] | undefined;
  isLoading: boolean;
  hideConfidence?: boolean;
}) {
  return (
    <div className="conversation-thread space-y-4 p-6">
      {isLoading ? <ThreadLoadingSkeleton /> : null}
      {!isLoading && messages ? (
        <ThreadMessages
          conversationId={conversationId}
          messages={messages}
          hideConfidence={hideConfidence}
        />
      ) : null}
    </div>
  );
}

function ThreadMessages({
  conversationId,
  messages,
  hideConfidence,
}: {
  conversationId: string | null;
  messages: ConversationMessage[];
  hideConfidence: boolean;
}) {
  // Длина на первом кадре треда: stagger только при входе, не на живых репликах.
  const [initialCount] = useState(messages.length);

  return (
    <>
      {messages.map((message, index) => {
        const stagger =
          index < initialCount
            ? Math.min(index, THREAD_ENTER_STAGGER_MAX) * THREAD_ENTER_STAGGER_MS
            : 0;
        return (
          <MessageBubble
            key={`${conversationId ?? "empty"}-${message.id}`}
            message={message}
            enterFrom={enterFromForRole(message.role)}
            enterDelayMs={stagger}
            hideConfidence={hideConfidence}
          />
        );
      })}
    </>
  );
}

function ThreadLoadingSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-2 text-sm text-secondary">
        <Spinner className="h-4 w-4" />
        <span>Загрузка диалога…</span>
      </div>
      <SkeletonBubble tone="user" />
      <SkeletonBubble tone="operator" />
      <SkeletonBubble tone="user" />
    </div>
  );
}

function SkeletonBubble({ tone }: { tone: "user" | "operator" }) {
  return (
    <div
      className={cn(
        "flex gap-3 rounded-[24px] border border-white/70 p-4",
        tone === "user" ? "bg-white/90" : "bg-primary/6",
      )}
    >
      <div className="thread-skeleton-bar h-11 w-11 shrink-0 rounded-full bg-slate-200/80" />
      <div className="min-w-0 flex-1 space-y-2 py-1">
        <div className="thread-skeleton-bar h-3 w-28 rounded-full bg-slate-200/90" />
        <div className="thread-skeleton-bar h-3 w-full rounded-full bg-slate-200/70" />
        <div className="thread-skeleton-bar h-3 w-4/5 rounded-full bg-slate-200/70" />
      </div>
    </div>
  );
}
