import { redirect } from "next/navigation";
import { OperatorPage } from "@/src/components/pages/operator-page";
import { getSession } from "@/src/lib/session";

export default async function OperatorRoute() {
  const user = await getSession();
  if (user?.role !== "operator") {
    redirect("/");
  }

  return <OperatorPage />;
}
