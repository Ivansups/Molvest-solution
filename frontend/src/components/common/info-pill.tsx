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
    <div className="rounded-[24px] border border-white/14 bg-white/10 p-4 backdrop-blur-xl transition-colors duration-200 hover:border-white/24 hover:bg-white/14">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/12 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]">
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-4 text-sm font-semibold text-white">{title}</p>
      <p className="mt-1 text-sm leading-6 text-white/68">{text}</p>
    </div>
  );
}
