import { redirect } from "next/navigation";
import { getSession } from "@/src/lib/session";

export default async function LegacyChatTicketRoute({
  params,
}: {
  params: Promise<{ ticketId: string }>;
}) {
  const { ticketId } = await params;
  const user = await getSession();
  if (user) {
    redirect(`/chat/support/${ticketId}`);
  }
  redirect("/chat");
}
