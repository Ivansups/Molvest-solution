import {
  Bot,
  Camera,
  Database,
  Headset,
  SearchCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { FlowRail, SignalTile } from "@/src/components/common/experience-primitives";
import { Button } from "@/src/components/ui/button";

function QuickTag({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-white/14 bg-white/10 px-3 py-1.5 text-xs text-white/76 backdrop-blur">
      {children}
    </span>
  );
}

export function GuestChatIntro() {
  return (
    <section className="dark-chameleon reveal-item flex min-h-[640px] flex-col justify-between overflow-hidden rounded-[38px] p-7 text-white lg:p-8">
      <div>
        <div className="flex flex-wrap gap-2">
          <span className="floating-chip">
            <Sparkles className="h-3.5 w-3.5" />
            GigaChat
          </span>
          <span className="floating-chip">
            <Headset className="h-3.5 w-3.5" />
            Оператор рядом
          </span>
        </div>
        <p className="mt-8 text-[11px] uppercase tracking-[0.24em] text-white/58">
          Гостевой доступ
        </p>
        <h1 className="mt-4 text-5xl font-semibold leading-[0.95] tracking-[-0.06em] text-balance lg:text-6xl xl:text-5xl">
          Ошибка 1С — в чат, решение — из базы знаний
        </h1>
        <p className="mt-5 max-w-xl text-base leading-8 text-white/72">
          Пользователь описывает проблему или прикладывает скриншот. Агент
          ищет ответ по материалам, а сложные случаи передаёт оператору.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <QuickTag>код ошибки</QuickTag>
          <QuickTag>форма 1С</QuickTag>
          <QuickTag>скриншот</QuickTag>
          <QuickTag>что нажали перед ошибкой</QuickTag>
        </div>
      </div>

      <div className="mt-8 grid gap-4">
        <div className="rounded-[28px] border border-white/12 bg-white/8 p-5 backdrop-blur-xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/52">
            Как идёт обращение
          </p>
          <FlowRail
            tone="dark"
            className="mt-5"
            items={[
              {
                title: "Вопрос или скриншот",
                text: "Чат принимает текст и изображение ошибки 1С.",
              },
              {
                title: "Ответ с источниками",
                text: "Агент показывает релевантные материалы базы знаний.",
              },
              {
                title: "Передача человеку",
                text: "Кнопка оператора остаётся в привычном месте и ведёт тот же сценарий.",
              },
            ]}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <SignalTile
            tone="dark"
            icon={Database}
            label="Источник"
            value="База знаний"
            text="Регламенты, инструкции и кейсы 1С."
          />
          <SignalTile
            tone="dark"
            icon={Camera}
            label="Вложения"
            value="PNG / JPEG"
            text="Скриншот остаётся частью обращения."
          />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[26px] border border-white/12 bg-white/10 p-4 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/12 text-white">
              <Bot className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-white">Для сотрудников</p>
              <p className="text-sm text-white/62">Очередь и база знаний после входа</p>
            </div>
          </div>
          <Button variant="outline" className="border-white/18 bg-white/12 text-white hover:bg-white/18" asChild>
            <Link href="/login">
              Войти
              <SearchCheck className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
