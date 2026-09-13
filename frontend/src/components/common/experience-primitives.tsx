import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/src/lib/utils";

export function PageHero({
  eyebrow,
  title,
  description,
  children,
  className,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("operator-topline p-6 lg:p-7", className)}>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="stage-kicker">{eyebrow}</p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-[-0.04em] text-secondary lg:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">
            {description}
          </p>
        </div>
        {children ? <div className="shrink-0">{children}</div> : null}
      </div>
    </section>
  );
}

export function SignalTile({
  icon: Icon,
  label,
  value,
  text,
  tone = "light",
}: {
  icon?: LucideIcon;
  label: string;
  value: string;
  text: string;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";

  return (
    <div
      className={cn(
        "signal-card p-4",
        dark && "signal-card-dark text-white shadow-none",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p
            className={cn(
              "text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400",
              dark && "text-white/50",
            )}
          >
            {label}
          </p>
          <p
            className={cn(
              "mt-2 text-lg font-semibold tracking-[-0.03em] text-secondary",
              dark && "text-white",
            )}
          >
            {value}
          </p>
        </div>
        {Icon ? (
          <span
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary",
              dark && "bg-white/12 text-white",
            )}
          >
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
      </div>
      <p className={cn("mt-3 text-sm leading-6 text-slate-500", dark && "text-white/66")}>
        {text}
      </p>
    </div>
  );
}

export function FlowRail({
  items,
  tone = "light",
  className,
}: {
  items: Array<{ title: string; text: string }>;
  tone?: "light" | "dark";
  className?: string;
}) {
  const dark = tone === "dark";

  return (
    <div className={cn("space-y-3", className)}>
      {items.map((item, index) => (
        <div key={item.title} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white shadow-[0_0_0_6px_rgba(33,160,56,0.12)]",
                dark && "bg-white text-secondary shadow-[0_0_0_6px_rgba(255,255,255,0.12)]",
              )}
            >
              {index + 1}
            </span>
            {index < items.length - 1 ? (
              <span
                className={cn(
                  "mt-2 h-full min-h-8 w-px bg-primary/18",
                  dark && "bg-white/18",
                )}
              />
            ) : null}
          </div>
          <div className="pb-2">
            <p className={cn("text-sm font-semibold text-secondary", dark && "text-white")}>
              {item.title}
            </p>
            <p className={cn("mt-1 text-sm leading-6 text-slate-500", dark && "text-white/64")}>
              {item.text}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

export function AmbientPanel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("chameleon-frame rounded-[30px] p-5", className)}>{children}</div>;
}
