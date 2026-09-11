import * as React from "react";
import { cn } from "@/src/lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex min-h-24 w-full rounded-[22px] border border-white/70 bg-white/90 px-4 py-3 text-sm text-foreground shadow-[0_8px_24px_rgba(27,51,85,0.05)] placeholder:text-[#70849a] focus-visible:ring-4 focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:bg-slate-50/90 disabled:text-slate-400",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export { Textarea };
