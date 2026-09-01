import { ChatPage } from "@/src/components/pages/chat-page";
import { getSession } from "@/src/lib/session";

export default async function SupportChatRoute() {
  const user = await getSession();
  return <ChatPage mode="support" user={user} />;
}
