import type { HTMLAttributes } from "react";
import { cn } from "@/src/lib/utils";

function Badge({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-white/75 bg-white/82 px-2.5 py-1 text-[11px] font-medium tracking-[0.02em] text-secondary shadow-[0_6px_18px_rgba(4,55,31,0.05)]",
        className,
      )}
      {...props}
    />
  );
}

export { Badge };
