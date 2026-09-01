import { Menu } from "lucide-react";
import { Outlet } from "react-router-dom";
import { AppHeader } from "@/src/components/common/app-header";
import { AppSidebar } from "@/src/components/common/app-sidebar";
import { Button } from "@/src/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/src/components/ui/sheet";
import { useApp } from "@/src/hooks/use-app-context";

export function AppShell() {
  const { currentUser } = useApp();

  if (!currentUser) {
    return null;
  }

  return (
    <div className="page-shell app-grid min-h-screen">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <div className="hidden lg:block">
          <AppSidebar role={currentUser.role} />
        </div>
        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-3 px-4 pt-4 lg:hidden">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0">
                <SheetHeader className="border-b border-border p-4">
                  <SheetTitle>Навигация</SheetTitle>
                </SheetHeader>
                <AppSidebar role={currentUser.role} />
              </SheetContent>
            </Sheet>
          </div>
          <AppHeader />
          <main className="flex-1 px-4 pb-8 pt-4 lg:px-8 lg:pb-10 lg:pt-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
