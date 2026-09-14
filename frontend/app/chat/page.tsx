import { ChatPage } from "@/src/components/pages/chat-page";
import { GuestChatIntro } from "@/src/components/pages/guest-chat-intro";
import { PublicPortalHeader } from "@/src/components/common/public-portal-header";
import { getSession } from "@/src/lib/session";

export const dynamic = "force-dynamic";

export default async function GuestChatRoute() {
  const user = await getSession();

  return (
    <div className="page-shell mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-8 lg:px-8">
      <PublicPortalHeader current="chat" signedIn={Boolean(user)} />
      <div className="grid items-start gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <GuestChatIntro />
        <ChatPage mode="guest" user={user} />
      </div>
    </div>
  );
}
