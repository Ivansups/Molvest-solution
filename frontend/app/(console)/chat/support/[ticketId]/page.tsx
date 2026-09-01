import { ChatPage } from "@/src/components/pages/chat-page";
import { getSession } from "@/src/lib/session";

export default async function SupportChatTicketRoute() {
  const user = await getSession();
  return <ChatPage detailMode mode="support" user={user} />;
}
