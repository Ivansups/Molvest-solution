import { BotMessageSquare } from "lucide-react";
import { cn } from "@/src/lib/utils";

export function BrandMark({
  compact = false,
  className,
  tone = "default",
}: {
  compact?: boolean;
  className?: string;
  tone?: "default" | "inverse";
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-primary via-[#08b861] to-secondary text-white shadow-sm">
        <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-white/80" />
        <BotMessageSquare className="h-5 w-5" />
      </div>
      <div className={compact ? "hidden sm:block" : "block"}>
        <div
          className={cn(
            "text-[11px] font-semibold uppercase tracking-[0.22em]",
            tone === "inverse" ? "text-white/70" : "text-primary",
          )}
        >
          Sber x Molvest
        </div>
        <div
          className={cn(
            "text-base font-semibold tracking-[-0.02em]",
            tone === "inverse" ? "text-white" : "text-secondary",
          )}
        >
          Техподдержка 1С
        </div>
      </div>
    </div>
  );
}
