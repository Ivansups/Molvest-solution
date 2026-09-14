import {
  Database,
  Headphones,
  LockKeyhole,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { redirect } from "next/navigation";
import { FlowRail, SignalTile } from "@/src/components/common/experience-primitives";
import { InfoPill } from "@/src/components/common/info-pill";
import { PublicPortalHeader } from "@/src/components/common/public-portal-header";
import { LoginForm } from "@/src/components/pages/login-form";
import { getSession } from "@/src/lib/session";

export const dynamic = "force-dynamic";

export default async function LoginRoute() {
  const user = await getSession();
  if (user) {
    redirect("/");
  }

  return (
    <div className="page-shell min-h-screen px-4 py-8 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <PublicPortalHeader current="login" signedIn={false} />
        <div className="grid items-stretch gap-6 lg:grid-cols-[minmax(0,1fr)_430px]">
          <section className="dark-chameleon reveal-item overflow-hidden rounded-[38px] p-7 text-white lg:p-10">
            <div className="flex min-h-[620px] flex-col justify-between gap-8">
              <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_280px]">
                <div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="floating-chip">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Закрытый контур
                    </span>
                    <span className="floating-chip">
                      <Sparkles className="h-3.5 w-3.5" />
                      GigaChat assist
                    </span>
                  </div>
                  <p className="mt-8 text-[11px] uppercase tracking-[0.24em] text-white/58">
                    Рабочее место поддержки
                  </p>
                  <h1 className="mt-4 max-w-3xl text-5xl font-semibold leading-[0.95] tracking-[-0.06em] text-balance lg:text-6xl">
                    Спокойная линия для сложных обращений 1С
                  </h1>
                  <p className="mt-5 max-w-2xl text-base leading-8 text-white/72">
                    Оператор видит диалог, контекст пользователя, источники базы
                    знаний и черновик ответа без ощущения технической админки.
                  </p>
                </div>
                <div className="rounded-[28px] border border-white/12 bg-white/8 p-5 backdrop-blur-xl">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/52">
                    Маршрут обращения
                  </p>
                  <FlowRail
                    tone="dark"
                    className="mt-5"
                    items={[
                      {
                        title: "Гость пишет в чат",
                        text: "Вопрос, ошибка 1С или скриншот попадают в общий поток.",
                      },
                      {
                        title: "Агент ищет решение",
                        text: "Ответ строится по базе знаний и дополняется источниками.",
                      },
                      {
                        title: "Оператор принимает сложное",
                        text: "Эскалации, черновики и закрытие диалога остаются рядом.",
                      },
                    ]}
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
                <InfoPill icon={Headphones} title="Очередь" text="Открытые и эскалированные диалоги" />
                <InfoPill icon={Database} title="База знаний" text="Документы и фрагменты для RAG" />
                <InfoPill icon={MessageSquareText} title="Ответ" text="Черновик рядом с перепиской" />
                <InfoPill icon={LockKeyhole} title="Доступ" text="Только сотрудники поддержки" />
              </div>
            </div>
          </section>
          <div className="flex flex-col gap-4">
            <LoginForm />
            <SignalTile
              icon={ShieldCheck}
              label="Локальный стенд"
              value="Готов к проверке"
              text="После входа откроется рабочий стол оператора с очередью, базой знаний и правилами ответа."
            />
          </div>
        </div>
      </div>
    </div>
  );
}
