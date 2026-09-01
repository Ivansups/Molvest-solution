import {
  BarChart3,
  Database,
  LayoutDashboard,
  LifeBuoy,
  MessageSquare,
  Settings,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { BrandMark } from "@/src/components/common/brand-mark";
import { cn } from "@/src/lib/utils";
import type { AppRole } from "@/src/types/domain";

const navigation: Array<{
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: AppRole[];
}> = [
  { to: "/", label: "Дашборд", icon: LayoutDashboard, roles: ["admin", "operator"] },
  { to: "/chat/support", label: "Чаты", icon: MessageSquare, roles: ["admin", "operator"] },
  { to: "/knowledge-base", label: "База знаний", icon: Database, roles: ["admin", "operator"] },
  { to: "/analytics", label: "Аналитика", icon: BarChart3, roles: ["admin", "operator"] },
  { to: "/settings", label: "Настройки", icon: Settings, roles: ["admin", "operator"] },
  { to: "/operator", label: "Операторская", icon: LifeBuoy, roles: ["operator"] },
];

export function AppSidebar({ role }: { role: AppRole }) {
  return (
    <aside className="accent-grid flex h-full w-72 flex-col border-r border-white/10 bg-[#10284d] px-5 py-6 text-white">
      <BrandMark />
      <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-3">
        <p className="text-[11px] uppercase tracking-[0.22em] text-white/55">
          Контур поддержки
        </p>
        <p className="mt-2 text-sm leading-6 text-white/80">
          GigaChat, база знаний, эскалации и операторские сценарии в одном
          рабочем пространстве.
        </p>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1.5">
        {navigation
          .filter((item) => item.roles.includes(role))
          .map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-white/72 transition-all hover:bg-white/8 hover:text-white",
                    isActive &&
                      "bg-gradient-to-r from-white/14 to-white/6 text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            );
          })}
      </nav>
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-white">Система активна</p>
          <span className="h-2.5 w-2.5 rounded-full bg-primary" />
        </div>
        <p className="mt-2 text-sm text-white/60">
          Публичный чат, RAG и admin-контур синхронизированы.
        </p>
      </div>
    </aside>
  );
}
