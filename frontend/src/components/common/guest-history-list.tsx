"use client";

import { CircleCheck, Headset, MessageCircle, RefreshCw } from "lucide-react";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { formatDateTime } from "@/src/lib/format";
import type { GuestHistoryItem, GuestHistoryStatus } from "@/src/lib/guest-session";
import { cn } from "@/src/lib/utils";

const STATUS_META: Record<
  GuestHistoryStatus,
  { label: string; chipClass: string }
> = {
  open: {
    label: "Открыт",
    chipClass: "border-primary/20 bg-primary/10 text-primary shadow-none",
  },
  escalated: {
    label: "Эскалирован",
    chipClass: "border-warning/30 bg-warning/10 text-warning shadow-none",
  },
  resolved: {
    label: "Закрыт",
    chipClass: "border-secondary/15 bg-secondary/8 text-secondary shadow-none",
  },
};

function previewText(preview: string): string {
  const trimmed = preview.trim();
  if (!trimmed) {
    return "Обращение";
  }
  if (trimmed.length <= 80) {
    return trimmed;
  }
  return `${trimmed.slice(0, 79).trimEnd()}…`;
}

/** Список обращений гостя: только id из localStorage этого браузера. */
export function GuestHistoryList({
  items,
  activeId,
  onSelect,
  onNew,
}: {
  items: GuestHistoryItem[];
  activeId: string | null;
  onSelect: (conversationId: string) => void;
  onNew: () => void;
}) {
  return (
    <div className="rounded-[24px] bg-white/92 p-5 shadow-[0_10px_24px_rgba(27,51,85,0.05)]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-primary">
            Мои обращения
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Только с этого браузера
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onNew}>
          <RefreshCw className="h-3.5 w-3.5" />
          Новый
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm leading-6 text-slate-500">
          Здесь появятся ваши обращения с этого устройства. Чужие чаты из базы
          не показываем.
        </p>
      ) : (
        <ScrollArea className="mt-4 max-h-[320px]">
          <div className="space-y-2 pr-3">
            {items.map((item) => {
              const isActive = item.id === activeId;
              const status = item.status;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-current={isActive ? "true" : undefined}
                  className={cn(
                    "w-full rounded-[18px] border bg-white p-3 text-left transition-colors",
                    "border-border hover:border-secondary/25 hover:bg-slate-50/70",
                    isActive &&
                      "border-secondary/40 bg-secondary/[0.04] shadow-[0_8px_20px_rgba(27,51,85,0.08)]",
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <span
                      className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
                      aria-hidden="true"
                    >
                      {status === "resolved" ? (
                        <CircleCheck className="h-4 w-4" />
                      ) : status === "escalated" ? (
                        <Headset className="h-4 w-4" />
                      ) : (
                        <MessageCircle className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-secondary">
                        {previewText(item.preview)}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <p className="min-w-0 flex-1 truncate text-xs text-slate-500">
                          {formatDateTime(item.updatedAt)}
                        </p>
                        {status ? (
                          <Badge className={cn("shrink-0", STATUS_META[status].chipClass)}>
                            {STATUS_META[status].label}
                          </Badge>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
