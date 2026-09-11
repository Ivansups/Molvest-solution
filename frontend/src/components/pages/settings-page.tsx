"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent } from "@/src/components/ui/card";
import { Label } from "@/src/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/src/components/ui/select";
import { Slider } from "@/src/components/ui/slider";
import { Spinner } from "@/src/components/ui/spinner";
import { useToast } from "@/src/hooks/use-toast";
import { settingsService } from "@/src/services/settings-service";

const schema = z.object({
  confidence_threshold: z.number().min(0.5).max(0.99),
  operator_assist_mode: z.enum(["draft", "auto", "agent"]),
});

type FormValues = z.infer<typeof schema>;

export function SettingsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsService.getSettings(),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      confidence_threshold: 0.8,
      operator_assist_mode: "draft",
    },
  });
  const confidenceThreshold = useWatch({
    control: form.control,
    name: "confidence_threshold",
  });

  useEffect(() => {
    const data = settingsQuery.data;
    if (!data) {
      return;
    }
    form.reset({
      confidence_threshold: data.confidence_threshold,
      operator_assist_mode: data.operator_assist_mode,
    });
  }, [form, settingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => settingsService.saveSettings(values),
    onSuccess: async (saved) => {
      form.reset(saved);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({
        title: "Настройки сохранены",
        description: "Порог и режим эскалации применены без рестарта API.",
      });
    },
    onError: (error) => {
      toast({
        title: "Не удалось сохранить",
        description: error instanceof Error ? error.message : "Ошибка API",
      });
    },
  });

  if (settingsQuery.isLoading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (!settingsQuery.data) {
    return (
      <ApiStateCard
        title="Настройки недоступны"
        description="Сервер не отдал GET /api/settings. Порог и режим пока только в env."
        detail={
          settingsQuery.error instanceof Error
            ? settingsQuery.error.message
            : undefined
        }
        actionHref="/"
        actionLabel="Вернуться в консоль"
      />
    );
  }

  const onSubmit = form.handleSubmit(async (values) => mutation.mutateAsync(values));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Настройки</h1>
        <p className="mt-2 text-slate-500">
          Порог уверенности и режим помощи оператору. Остальное — через переменные
          окружения.
        </p>
      </div>
      <Card>
        <CardContent className="space-y-8 pt-6">
          <form onSubmit={onSubmit} className="space-y-8">
            <div className="rounded-xl border border-border p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-secondary">Порог уверенности</p>
                  <p className="text-sm text-slate-500">
                    Текущий порог: {Math.round((confidenceThreshold ?? 0.8) * 100)}%
                  </p>
                </div>
              </div>
              <Controller
                control={form.control}
                name="confidence_threshold"
                render={({ field }) => (
                  <Slider
                    value={[field.value]}
                    min={0.5}
                    max={0.99}
                    step={0.01}
                    className="mt-4"
                    onValueChange={(value) => field.onChange(value[0] ?? 0.8)}
                  />
                )}
              />
            </div>
            <div className="grid gap-2">
              <Label>Режим помощи оператору</Label>
              <Controller
                control={form.control}
                name="operator_assist_mode"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Режим" />
                    </SelectTrigger>
                    <SelectContent className="max-w-[min(36rem,calc(100vw-2rem))]">
                      <SelectItem value="auto" className="whitespace-normal">
                        Если уверен — отвечает гостю сразу; после эскалации тоже
                        может ответить сам
                      </SelectItem>
                      <SelectItem value="draft" className="whitespace-normal">
                        Если уверен — отвечает гостю сразу; после эскалации —
                        только черновик оператору
                      </SelectItem>
                      <SelectItem value="agent" className="whitespace-normal">
                        ИИ никогда не пишет в чат гостя, пока оператор не нажмёт
                        Отправить
                      </SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={mutation.isPending}>
                Применить
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
