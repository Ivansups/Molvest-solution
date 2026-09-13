import { redirect } from "next/navigation";
import { LogsPage } from "@/src/components/pages/logs-page";
import { getSession } from "@/src/lib/session";

export default async function LogsRoute() {
  const user = await getSession();
  if (!user) {
    redirect("/login");
  }
  return <LogsPage installationId={user.installationId} />;
}
