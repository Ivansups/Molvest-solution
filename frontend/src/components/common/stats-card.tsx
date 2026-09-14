import type { LucideIcon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";

export function StatsCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card className="group overflow-hidden rounded-[28px] border-white/80 bg-white/72">
      <CardHeader className="relative flex flex-row items-start justify-between space-y-0 pb-3">
        <span className="absolute left-6 top-0 h-1.5 w-16 rounded-b-full bg-[linear-gradient(90deg,var(--primary),#00c2a8)]" />
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <CardTitle className="mt-2 text-3xl tracking-[-0.05em]">
            {value}
          </CardTitle>
        </div>
        <div className="rounded-2xl border border-primary/10 bg-primary/10 p-3 text-primary transition-transform duration-200 group-hover:-translate-y-0.5">
          <Icon className="h-5 w-5" />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6 text-slate-500">{hint}</p>
      </CardContent>
    </Card>
  );
}
