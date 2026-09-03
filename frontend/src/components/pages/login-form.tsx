"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { loginAction } from "@/src/actions/auth";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Checkbox } from "@/src/components/ui/checkbox";
import { Input } from "@/src/components/ui/input";
import { Label } from "@/src/components/ui/label";
import { useToast } from "@/src/hooks/use-toast";

const schema = z.object({
  email: z.string().email("Введите корректный email"),
  password: z.string().min(6, "Минимум 6 символов"),
  remember: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

export function LoginForm() {
  const { toast } = useToast();
  const router = useRouter();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
      remember: true,
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    try {
      const redirectTo = await loginAction(
        values.email,
        values.password,
        values.remember,
      );
      toast({
        title: "Авторизация выполнена",
        description: "Открываем панель поддержки.",
      });
      router.push(redirectTo);
      router.refresh();
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
            <Link href="/chat">Открыть гостевой чат</Link>
          </Button>
        </form>
        <div className="mt-4 rounded-[20px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
          Для локального просмотра панели:
          <br />
          `operator@molvest.ru / password123` или `admin@molvest.ru / password123`
        </div>
        <div className="mt-6 rounded-[22px] border border-border/70 bg-slate-50/80 p-4 text-sm text-slate-500">
          Поддержка: support@molvest.ru
          <br />
          Линия 1: +7 (473) 000-00-00
        </div>
      </CardContent>
    </Card>
  );
}
