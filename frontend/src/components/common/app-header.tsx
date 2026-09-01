import { Bell, LogOut, Search, UserCircle2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Avatar, AvatarFallback } from "@/src/components/ui/avatar";
import { Button } from "@/src/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/src/components/ui/dropdown-menu";
import { Input } from "@/src/components/ui/input";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { useApp } from "@/src/hooks/use-app-context";
import { formatDateTime } from "@/src/lib/format";

export function AppHeader() {
  const navigate = useNavigate();
  const { currentUser, notifications, logout } = useApp();

  return (
    <header className="px-4 pt-4 lg:px-8">
      <div className="shell-panel soft-shadow flex items-center gap-4 rounded-[22px] border border-white/70 px-4 py-4">
        <div className="hidden min-w-0 xl:block">
          <p className="text-[11px] uppercase tracking-[0.2em] text-primary">
            Support Console
          </p>
          <p className="mt-1 text-sm font-medium text-secondary">
            AI-агент для техподдержки 1С и операторского контура
          </p>
        </div>
        <div className="relative max-w-xl flex-1">
        <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <Input
          placeholder="Поиск по чатам, документам и логам"
          className="h-11 rounded-2xl border-white/60 bg-white/80 pl-9"
        />
        </div>
        <Button
          variant="outline"
          className="hidden rounded-2xl border-white/60 bg-white/80 lg:inline-flex"
          asChild
        >
          <Link to="/chat">Гостевой чат</Link>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="rounded-2xl border-white/60 bg-white/80"
            >
              <Bell className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>Уведомления</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <ScrollArea className="h-64">
              {notifications.length ? (
                <div className="space-y-2 p-1">
                  {notifications.map((item) => (
                    <div key={item.id} className="rounded-lg border border-border p-3">
                      <p className="text-sm font-medium text-secondary">{item.title}</p>
                      <p className="mt-1 text-sm text-slate-500">{item.description}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {formatDateTime(item.createdAt)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-4 text-sm text-slate-500">
                  Новых уведомлений нет.
                </div>
              )}
            </ScrollArea>
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-3 rounded-2xl border border-white/60 bg-white/80 px-3 py-2 text-left">
              <Avatar className="h-9 w-9">
                <AvatarFallback>
                  {currentUser?.name
                    .split(" ")
                    .map((part) => part[0])
                    .join("")
                    .slice(0, 2)}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:block">
                <p className="text-sm font-medium text-secondary">
                  {currentUser?.name}
                </p>
                <p className="text-xs text-slate-500">{currentUser?.role}</p>
              </div>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Профиль</DropdownMenuLabel>
            <DropdownMenuItem>
              <UserCircle2 className="h-4 w-4" />
              {currentUser?.email}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
              Выйти
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
