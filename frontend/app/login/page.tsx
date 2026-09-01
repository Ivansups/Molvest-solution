import { LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import { redirect } from "next/navigation";
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
                <div className="rounded-[24px] border border-white/10 bg-[#0d2448]/58 p-4 backdrop-blur">
                  <ShieldCheck className="h-5 w-5 text-white" />
                  <p className="mt-4 text-sm font-medium text-white">
                    Защищённый доступ
                  </p>
                  <p className="mt-1 text-sm leading-6 text-white/70">
                    Только учётные записи поддержки
                  </p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-[#0d2448]/58 p-4 backdrop-blur">
                  <Sparkles className="h-5 w-5 text-white" />
                  <p className="mt-4 text-sm font-medium text-white">RAG + Vision</p>
                  <p className="mt-1 text-sm leading-6 text-white/70">
                    Ответы и анализ скриншотов 1С
                  </p>
                </div>
                <div className="rounded-[24px] border border-white/10 bg-[#0d2448]/58 p-4 backdrop-blur">
                  <LockKeyhole className="h-5 w-5 text-white" />
                  <p className="mt-4 text-sm font-medium text-white">Единый контур</p>
                  <p className="mt-1 text-sm leading-6 text-white/70">
                    Чаты, документы, аналитика
                  </p>
                </div>
              </div>
            </div>
          </section>
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
