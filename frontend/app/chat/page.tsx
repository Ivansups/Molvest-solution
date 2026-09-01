import { ChatPage } from "@/src/components/pages/chat-page";
import { GuestChatIntro } from "@/src/components/pages/guest-chat-intro";
import { PublicPortalHeader } from "@/src/components/common/public-portal-header";
import { getSession } from "@/src/lib/session";

export default async function GuestChatRoute() {
  const user = await getSession();

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-8 lg:px-0">
      <PublicPortalHeader current="chat" signedIn={Boolean(user)} />
      <GuestChatIntro />
      <ChatPage mode="guest" user={user} />
    </div>
  );
}
