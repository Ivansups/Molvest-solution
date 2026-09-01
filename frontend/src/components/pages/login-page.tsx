import { zodResolver } from "@hookform/resolvers/zod";
import { LockKeyhole, ShieldCheck, Sparkles } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";
import { PublicPortalHeader } from "@/src/components/common/public-portal-header";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Checkbox } from "@/src/components/ui/checkbox";
import { Input } from "@/src/components/ui/input";
import { Label } from "@/src/components/ui/label";
import { useApp } from "@/src/hooks/use-app-context";
import { useToast } from "@/src/hooks/use-toast";

const schema = z.object({
  email: z.string().email("Введите корректный email"),
  password: z.string().min(6, "Минимум 6 символов"),
  remember: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const { currentUser, login } = useApp();
  const { toast } = useToast();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
      remember: false,
    },
  });

  if (currentUser) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = form.handleSubmit(async (values) => {
    try {
      await login(values.email, values.password);
      toast({
        title: "Авторизация выполнена",
        description: "Рабочее место AI-агента готово к работе.",
      });
      navigate("/");
    } catch (error) {
      toast({
        title: "Не удалось войти",
        description:
          error instanceof Error ? error.message : "Проверьте учётные данные.",
        variant: "destructive",
      });
    }
  });

  return (
    <div className="page-shell min-h-screen px-4 py-8 lg:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <PublicPortalHeader current="login" />
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
          <Card className="shell-panel w-full rounded-[32px]">
          <CardHeader className="items-start border-b border-border/60 pb-5">
            <p className="rounded-full bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
              Только для сотрудников
            </p>
            <CardTitle className="mt-5 text-2xl">Вход для поддержки</CardTitle>
            <CardDescription>
              Внутренняя панель администрирования и операторской работы
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form className="space-y-5" onSubmit={handleSubmit}>
              <div className="grid gap-2">
                <Label htmlFor="email">Корпоративный email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="operator@molvest.ru"
                  autoComplete="email"
                  {...form.register("email")}
                />
                <p className="text-sm text-destructive">
                  {form.formState.errors.email?.message}
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="password">Пароль</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Введите пароль"
                  autoComplete="current-password"
                  {...form.register("password")}
                />
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <Controller
                      control={form.control}
                      name="remember"
                      render={({ field }) => (
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={(checked) => field.onChange(Boolean(checked))}
                        />
                      )}
                    />
                    <span className="text-slate-500">Запомнить меня</span>
                  </div>
                  <a href="mailto:support@molvest.ru" className="text-primary hover:underline">
                    Нужен доступ?
                  </a>
                </div>
              </div>
              <Button type="submit" className="w-full">
                Войти в панель
              </Button>
              <Button type="button" variant="outline" className="w-full" asChild>
                <Link to="/chat">Открыть гостевой чат</Link>
              </Button>
            </form>
            <div className="mt-4 rounded-[20px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
              Для локального просмотра панели:
              <br />
              `operator@molvest.ru / password` или `admin@molvest.ru / password`
            </div>
            <div className="mt-6 rounded-[22px] border border-border/70 bg-slate-50/80 p-4 text-sm text-slate-500">
              Поддержка: support@molvest.ru
              <br />
              Линия 1: +7 (473) 000-00-00
            </div>
          </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
