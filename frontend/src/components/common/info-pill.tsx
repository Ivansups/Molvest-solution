import type { LucideIcon } from "lucide-react";

export function InfoPill({
  title,
  text,
  icon: Icon,
}: {
  title: string;
  text: string;
  icon: LucideIcon;
}) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-[#0d2448]/58 p-4 backdrop-blur">
      <Icon className="h-5 w-5 text-white" />
      <p className="mt-4 text-sm font-medium text-white">{title}</p>
      <p className="mt-1 text-sm leading-6 text-white/70">{text}</p>
    </div>
  );
}
