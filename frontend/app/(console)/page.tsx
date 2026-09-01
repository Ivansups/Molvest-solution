import { redirect } from "next/navigation";
import { DashboardPage } from "@/src/components/pages/dashboard-page";
import { getSession } from "@/src/lib/session";
import { loadDashboard } from "@/src/lib/server-api";

export default async function HomePage() {
  const user = await getSession();
  if (!user) {
    redirect("/chat");
  }

  const data = await loadDashboard(user.installationId);
  return (
    <DashboardPage health={data.health} documents={data.documents} />
  );
}
