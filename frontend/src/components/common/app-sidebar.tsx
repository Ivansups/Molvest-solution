"use client";

import {
  BarChart3,
  Database,
  LayoutDashboard,
  MessageSquare,
  ScrollText,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandMark } from "@/src/components/common/brand-mark";
import { cn } from "@/src/lib/utils";
import type { AppRole } from "@/src/types/domain";

function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

const navigation: Array<{
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: AppRole[];
}> = [
  { to: "/", label: "Рабочий стол", icon: LayoutDashboard, roles: ["admin", "operator"] },
  { to: "/chat/support", label: "Диалоги", icon: MessageSquare, roles: ["admin", "operator"] },
  { to: "/knowledge-base", label: "База знаний", icon: Database, roles: ["admin", "operator"] },
  { to: "/analytics", label: "Аналитика", icon: BarChart3, roles: ["admin", "operator"] },
  { to: "/logs", label: "История", icon: ScrollText, roles: ["admin", "operator"] },
  { to: "/settings", label: "Правила ответа", icon: Settings, roles: ["admin", "operator"] },
];

export function AppSidebar({ role }: { role: AppRole }) {
  const pathname = usePathname();

  return (
    <aside className="operator-sidebar ui-surface accent-grid flex h-full w-72 flex-col border-r border-white/10 px-5 py-6 text-white">
      <BrandMark tone="inverse" />
      <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-3">
        <p className="text-[11px] uppercase tracking-[0.22em] text-white/55">
          Рабочая линия
        </p>
        <p className="mt-2 text-sm leading-6 text-white/80">
          Очередь обращений, база знаний и подсказки GigaChat в одном
          спокойном рабочем месте.
        </p>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1.5">
        {navigation
          .filter((item) => item.roles.includes(role))
          .map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                href={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-white/72 transition-all hover:bg-white/10 hover:text-white",
                  isNavActive(pathname, item.to) &&
                    "bg-gradient-to-r from-white/16 via-white/10 to-white/6 text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1)]",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
      </nav>
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-white">Система активна</p>
          <span className="h-2.5 w-2.5 rounded-full bg-primary" />
        </div>
        <p className="mt-2 text-sm text-white/60">
          Публичный чат, RAG и рабочее место синхронизированы.
        </p>
      </div>
    </aside>
  );
}
