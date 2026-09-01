import * as React from "react";
import { cn } from "@/src/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-2xl border border-white/70 bg-white/90 px-4 py-2 text-sm text-foreground shadow-[0_8px_24px_rgba(27,51,85,0.05)] placeholder:text-[#70849a] focus-visible:ring-4 focus-visible:ring-ring/40",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
