"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent } from "@/src/components/ui/card";
import { Slider } from "@/src/components/ui/slider";
import { Spinner } from "@/src/components/ui/spinner";
import { Switch } from "@/src/components/ui/switch";
import { useToast } from "@/src/hooks/use-toast";
import { cn } from "@/src/lib/utils";
import { settingsService } from "@/src/services/settings-service";
import type { OperatorAssistMode } from "@/src/types/api";

const schema = z.object({
  confidence_threshold: z.number().min(0.5).max(0.99),
  operator_assist_mode: z.enum(["draft", "auto", "agent"]),
  escalate_on_detector_failure: z.boolean(),
  escalate_on_low_rag: z.boolean(),
  skip_low_rag_on_image: z.boolean(),
  escalate_on_guest_handoff: z.boolean(),
});

const ESCALATION_RULES: {
  name:
    | "escalate_on_detector_failure"
    | "escalate_on_low_rag"
    | "skip_low_rag_on_image"
    | "escalate_on_guest_handoff";
  label: string;
  description: string;
}[] = [
  {
    name: "escalate_on_low_rag",
    label: "Слабый поиск в базе",
    description:
      "Если в базе нет подходящих фрагментов или уверенность ниже порога — передать оператору.",
  },
  {
    name: "skip_low_rag_on_image",
    label: "Не эскалировать скриншот при слабом поиске",
    description:
      "По скриншоту 1С всё равно ответить, даже если база не нашла похожий фрагмент.",
  },
  {
    name: "escalate_on_guest_handoff",
    label: "Просьба гостя позвать оператора",
    description:
      "Фразы вроде «позовите оператора» сразу передают диалог человеку.",
  },
  {
    name: "escalate_on_detector_failure",
    label: "Сбой классификатора",
    description:
      "Если не удалось понять запрос (сбой моделей) — безопаснее передать оператору, чем отвечать наугад.",
  },
];

const ASSIST_MODES: {
  value: OperatorAssistMode;
  label: string;
  description: string;
}[] = [
  {
    value: "draft",
    label: "Черновик",
    description:
      "Если уверен — отвечает гостю сразу; после эскалации — только черновик оператору.",
  },
  {
    value: "auto",
    label: "Авто",
    description:
      "Если уверен — отвечает гостю сразу; после эскалации тоже может ответить сам.",
  },
  {
    value: "agent",
    label: "Агент",
    description:
      "ИИ никогда не пишет в чат гостя, пока оператор не нажмёт «Отправить».",
  },
];

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
      operator_assist_mode: "auto",
      escalate_on_detector_failure: true,
      escalate_on_low_rag: true,
      skip_low_rag_on_image: true,
      escalate_on_guest_handoff: true,
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
      escalate_on_detector_failure: data.escalate_on_detector_failure,
      escalate_on_low_rag: data.escalate_on_low_rag,
      skip_low_rag_on_image: data.skip_low_rag_on_image,
      escalate_on_guest_handoff: data.escalate_on_guest_handoff,
    });
  }, [form, settingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => settingsService.saveSettings(values),
    onSuccess: async (saved) => {
      form.reset(saved);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast({
        title: "Настройки сохранены",
        description: "Порог, режим и правила эскалации применены без рестарта API.",
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
        title="Правила ответа недоступны"
        description="Рабочие правила временно недоступны. Порог и режим пока нельзя изменить из интерфейса."
        detail={
          settingsQuery.error instanceof Error
            ? settingsQuery.error.message
            : undefined
        }
        actionHref="/"
        actionLabel="Вернуться на рабочий стол"
      />
    );
  }

  const onSubmit = form.handleSubmit(async (values) => mutation.mutateAsync(values));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Правила ответа</h1>
        <p className="mt-2 text-slate-500">
          Как агент отвечает сам, когда готовит черновик и когда передаёт диалог
          оператору.
        </p>
      </div>
      <Card>
        <CardContent className="space-y-8 pt-6">
          <form onSubmit={onSubmit} className="space-y-8">
            <div className="rounded-[24px] border border-primary/10 bg-white/64 p-5">
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
            <div className="rounded-[24px] border border-primary/10 bg-white/64 p-5">
              <p className="font-medium text-secondary">Режим помощи оператору</p>
              <p className="mt-1 text-sm text-slate-500">
                Кто отвечает гостю: бот, черновик оператору или только после
                «Отправить».
              </p>
              <Controller
                control={form.control}
                name="operator_assist_mode"
                render={({ field }) => (
                  <div
                    role="radiogroup"
                    aria-label="Режим помощи оператору"
                    className="mt-4 grid gap-3 md:grid-cols-3"
                  >
                    {ASSIST_MODES.map((mode) => {
                      const selected = field.value === mode.value;
                      return (
                        <button
                          key={mode.value}
                          type="button"
                          role="radio"
                          aria-checked={selected}
                          onClick={() => field.onChange(mode.value)}
                          className={cn(
                            "rounded-[20px] border p-4 text-left transition-colors",
                            selected
                              ? "border-primary bg-primary/10 shadow-[0_10px_26px_rgba(33,160,56,0.12)]"
                              : "border-border bg-white/80 hover:border-primary/40",
                          )}
                        >
                          <p className="font-medium text-secondary">{mode.label}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            {mode.description}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                )}
              />
            </div>
            <div className="rounded-[24px] border border-primary/10 bg-white/64 p-5">
              <p className="font-medium text-secondary">Правила эскалации</p>
              <p className="mt-1 text-sm text-slate-500">
                Когда передавать вопрос оператору, кроме порога уверенности.
              </p>
              <div className="mt-4 space-y-4">
                {ESCALATION_RULES.map((rule) => (
                  <Controller
                    key={rule.name}
                    control={form.control}
                    name={rule.name}
                    render={({ field }) => (
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-secondary">{rule.label}</p>
                          <p className="mt-1 text-sm text-slate-500">
                            {rule.description}
                          </p>
                        </div>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          aria-label={rule.label}
                        />
                      </div>
                    )}
                  />
                ))}
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={mutation.isPending}>
                Применить правила
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
