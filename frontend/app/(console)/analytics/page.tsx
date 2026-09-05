import { AnalyticsPage } from "@/src/components/pages/analytics-page";
import { getSession } from "@/src/lib/session";
import { loadAnalytics } from "@/src/lib/server-api";

export default async function AnalyticsRoute() {
  const user = await getSession();
  const data = await loadAnalytics(user!.installationId);
  return <AnalyticsPage metrics={data.metrics} trends={data.trends} />;
}
