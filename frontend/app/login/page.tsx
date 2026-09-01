import { LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import { redirect } from "next/navigation";
import { InfoPill } from "@/src/components/common/info-pill";
import { PublicPortalHeader } from "@/src/components/common/public-portal-header";
import { LoginForm } from "@/src/components/pages/login-form";
import { getSession } from "@/src/lib/session";

export default async function LoginRoute() {
  const user = await getSession();
  if (user) {
    redirect("/");
  }

  return (
    <div className="page-shell min-h-screen px-4 py-8 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <PublicPortalHeader current="login" signedIn={false} />
        <div className="grid gap-6 lg:grid-cols-[1.06fr_0.94fr]">
          <section className="hero-panel soft-shadow relative overflow-hidden rounded-[32px] p-8 text-white lg:p-10">
            <div className="relative z-10 flex h-full flex-col justify-between gap-10">
              <div className="max-w-xl">
                <p className="text-[11px] uppercase tracking-[0.22em] text-white/60">
                  Закрытый контур поддержки
                </p>
                <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-[-0.04em] text-balance">
                  Управление базой знаний, эскалациями и ответами GigaChat
                </h1>
                <p className="mt-4 max-w-lg text-sm leading-7 text-white/74">
                  Защищённая панель для сотрудников поддержки 1С: чаты, операторский
                  поток, аналитика и документы базы знаний в одном рабочем контуре.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <InfoPill
                  icon={ShieldCheck}
                  title="Защищённый доступ"
                  text="Только учётные записи поддержки"
                />
                <InfoPill
                  icon={Sparkles}
                  title="RAG + Vision"
                  text="Ответы и анализ скриншотов 1С"
                />
                <InfoPill
                  icon={LockKeyhole}
                  title="Единый контур"
                  text="Чаты, документы, аналитика"
                />
              </div>
            </div>
          </section>
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
