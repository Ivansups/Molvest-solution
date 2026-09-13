import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/src/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-medium transition-all duration-200 disabled:pointer-events-none disabled:opacity-50 focus-visible:ring-4 focus-visible:ring-ring/40",
  {
    variants: {
      variant: {
        default:
          "bg-[linear-gradient(135deg,var(--primary),#00b884_48%,#087343)] text-primary-foreground shadow-[0_14px_30px_rgba(33,160,56,0.24)] hover:-translate-y-0.5 hover:shadow-[0_18px_38px_rgba(33,160,56,0.3)]",
        secondary:
          "bg-secondary text-secondary-foreground shadow-[0_10px_24px_rgba(7,53,37,0.2)] hover:-translate-y-0.5 hover:bg-secondary/92",
        outline:
          "border-[1.5px] border-primary/20 bg-white/62 text-secondary shadow-none hover:border-primary/45 hover:bg-primary/7",
        ghost: "text-foreground hover:bg-primary/7 hover:text-secondary",
        destructive:
          "bg-destructive text-white hover:bg-destructive/90",
      },
      size: {
        default: "h-11 px-4 py-2",
        sm: "h-9 rounded-xl px-3",
        lg: "h-12 px-6",
        icon: "h-11 w-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
