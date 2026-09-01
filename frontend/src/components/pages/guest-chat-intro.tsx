import { Bot, Database, SearchCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { InfoPill } from "@/src/components/common/info-pill";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent } from "@/src/components/ui/card";

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-border/60 bg-white/80 p-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 text-sm font-medium text-secondary">{value}</p>
    </div>
  );
}

export function GuestChatIntro() {
  return (
    <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <div className="hero-panel soft-shadow overflow-hidden rounded-[30px] p-8 text-white lg:p-10">
        <div className="max-w-2xl">
          <p className="text-[11px] uppercase tracking-[0.24em] text-white/60">
            Гостевой доступ
          </p>
          <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-[-0.04em] text-balance">
            Гостевой чат по вопросам 1С
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-7 text-white/72">
            Пользовательский канал без авторизации для текстовых обращений и
            загрузки скриншотов ошибок. Закрытая панель поддержки остаётся
            отдельным защищённым контуром.
          </p>
        </div>
        <div className="mt-10 grid gap-3 sm:grid-cols-3">
          <InfoPill
            icon={Database}
            title="База знаний"
            text="Регламенты, кейсы и инструкции 1С"
          />
          <InfoPill
            icon={SearchCheck}
            title="RAG-поиск"
            text="Подбор релевантных фрагментов перед ответом"
          />
          <InfoPill
            icon={Sparkles}
            title="GigaChat"
            text="Генерация ответа и Vision-анализ скриншотов"
          />
        </div>
      </div>
      <div className="grid gap-4">
        <Card className="shell-panel rounded-[30px]">
          <CardContent className="grid gap-4 p-6">
            <div>
              <p className="text-[11px] uppercase tracking-[0.22em] text-primary">
                Контур работы
              </p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-secondary">
                Публичный чат связан с закрытой support-панелью
              </h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <MiniStat label="Канал" value="Web Widget" />
              <MiniStat label="Модель" value="GigaChat" />
              <MiniStat label="Вложения" value="PNG / JPEG" />
              <MiniStat label="Маршрут" value="Chat → RAG" />
            </div>
            <div className="rounded-[24px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-secondary">
                    Закрытый контур для сотрудников
                  </p>
                  <p className="text-sm text-slate-500">
                    База знаний, операторская и аналитика доступны только после входа
                  </p>
                </div>
              </div>
              <Button variant="outline" className="mt-4 w-full sm:w-auto" asChild>
                <Link href="/login">Перейти ко входу поддержки</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
        <Card className="shell-panel rounded-[30px]">
          <CardContent className="p-6">
            <p className="text-[11px] uppercase tracking-[0.22em] text-primary">
              Что поможет ответу
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge>Код ошибки</Badge>
              <Badge>Название формы 1С</Badge>
              <Badge>Действие пользователя</Badge>
              <Badge>Скриншот экрана</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
