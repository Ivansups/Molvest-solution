import {
  ArrowUpRight,
  LayoutDashboard,
  LockKeyhole,
  MessageSquareText,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { BrandMark } from "@/src/components/common/brand-mark";
import { Button } from "@/src/components/ui/button";
import { useApp } from "@/src/hooks/use-app-context";
import { cn } from "@/src/lib/utils";

export function PublicPortalHeader({
  current,
  className,
}: {
  current: "chat" | "login";
  className?: string;
}) {
  const { currentUser } = useApp();

  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <BrandMark compact />
      <div className="flex flex-wrap items-center gap-3">
        <div className="shell-panel soft-shadow inline-flex items-center gap-1 rounded-full border border-white/70 p-1">
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
                current === "chat" || isActive
                  ? "bg-secondary !text-white shadow-[0_10px_24px_rgba(26,59,107,0.18)]"
                  : "text-slate-500 hover:text-secondary",
              )
            }
          >
            <MessageSquareText className="h-4 w-4" />
            Гостевой чат
          </NavLink>
          <NavLink
            to={currentUser ? "/" : "/login"}
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
                current === "login" || isActive
                  ? "bg-secondary !text-white shadow-[0_10px_24px_rgba(26,59,107,0.18)]"
                  : "text-slate-500 hover:text-secondary",
              )
            }
          >
            {currentUser ? (
              <LayoutDashboard className="h-4 w-4" />
            ) : (
              <LockKeyhole className="h-4 w-4" />
            )}
            {currentUser ? "Панель поддержки" : "Вход поддержки"}
          </NavLink>
        </div>
        {currentUser ? (
          <Button variant="outline" asChild>
            <Link to="/">
              <ArrowUpRight className="h-4 w-4" />
              Открыть консоль
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
