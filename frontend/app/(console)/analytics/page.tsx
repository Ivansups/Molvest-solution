import { redirect } from "next/navigation";
import { AnalyticsPage } from "@/src/components/pages/analytics-page";
import { getSession } from "@/src/lib/session";

export default async function AnalyticsRoute() {
  const user = await getSession();
  if (!user) {
    redirect("/login");
  }
  return <AnalyticsPage installationId={user.installationId} />;
}
