import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { AppShell } from "@/src/components/common/app-shell";
import { getSession } from "@/src/lib/session";

export const dynamic = "force-dynamic";

export default async function ConsoleLayout({
  children,
}: {
  children: ReactNode;
}) {
  const user = await getSession();
  if (!user) {
    redirect("/login");
  }

  return <AppShell user={user}>{children}</AppShell>;
}
