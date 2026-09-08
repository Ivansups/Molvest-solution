import {
  ArrowUpRight,
  LayoutDashboard,
  LockKeyhole,
  MessageSquareText,
} from "lucide-react";
import Link from "next/link";
import { BrandMark } from "@/src/components/common/brand-mark";
import { Button } from "@/src/components/ui/button";
import { cn } from "@/src/lib/utils";

export function PublicPortalHeader({
  current,
  className,
  signedIn = false,
}: {
  current: "chat" | "login";
  className?: string;
  signedIn?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
    >
      <BrandMark compact />
      <div className="flex flex-wrap items-center gap-3">
        <div className="ui-surface shell-panel soft-shadow inline-flex items-center gap-1 rounded-full border border-white/70 p-1">
          <Link
            href="/chat"
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
              current === "chat"
                ? "bg-secondary !text-white shadow-[0_10px_24px_rgba(26,59,107,0.18)]"
                : "text-slate-500 hover:text-secondary",
            )}
          >
            <MessageSquareText className="h-4 w-4" />
            Гостевой чат
          </Link>
          <Link
            href={signedIn ? "/" : "/login"}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors",
              current === "login"
                ? "bg-secondary !text-white shadow-[0_10px_24px_rgba(26,59,107,0.18)]"
                : "text-slate-500 hover:text-secondary",
            )}
          >
            {signedIn ? (
              <LayoutDashboard className="h-4 w-4" />
            ) : (
              <LockKeyhole className="h-4 w-4" />
            )}
            {signedIn ? "Панель поддержки" : "Вход поддержки"}
          </Link>
        </div>
        {signedIn ? (
          <Button variant="outline" asChild>
            <Link href="/">
              <ArrowUpRight className="h-4 w-4" />
              Открыть консоль
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
