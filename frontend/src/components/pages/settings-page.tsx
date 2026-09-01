import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import { Label } from "@/src/components/ui/label";
import { Slider } from "@/src/components/ui/slider";
import { Spinner } from "@/src/components/ui/spinner";
import { Switch } from "@/src/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/src/components/ui/tabs";
import { useToast } from "@/src/hooks/use-toast";
import { settingsService } from "@/src/services/settings-service";

const schema = z.object({
  workspaceName: z.string().min(2),
  supportEmail: z.string().email(),
  autoReplyEnabled: z.boolean(),
  responseSlaSeconds: z.number().min(1).max(30),
  confidenceThreshold: z.number().min(0.5).max(0.99),
  autoConnectEnabled: z.boolean(),
  defaultQueue: z.string().min(2),
  bitrixWebhook: z.string().url(),
  redmineMailbox: z.string().email(),
  syncEmailCases: z.boolean(),
  generationModel: z.string().min(2),
  embeddingsModel: z.string().min(2),
  visionEnabled: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

export function SettingsPage() {
  const { toast } = useToast();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsService.getSettings(),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
  });
  const confidenceThreshold = useWatch({
    control: form.control,
    name: "confidenceThreshold",
  });

  useEffect(() => {
    const data = settingsQuery.data;
    if (!data) {
      return;
    }

    form.reset({
      workspaceName: data.general.workspaceName,
      supportEmail: data.general.supportEmail,
      autoReplyEnabled: data.general.autoReplyEnabled,
      responseSlaSeconds: data.general.responseSlaSeconds,
      confidenceThreshold: data.escalation.confidenceThreshold,
      autoConnectEnabled: data.escalation.autoConnectEnabled,
      defaultQueue: data.escalation.defaultQueue,
      bitrixWebhook: data.integrations.bitrixWebhook,
      redmineMailbox: data.integrations.redmineMailbox,
      syncEmailCases: data.integrations.syncEmailCases,
      generationModel: data.models.generationModel,
      embeddingsModel: data.models.embeddingsModel,
      visionEnabled: data.models.visionEnabled,
    });
  }, [form, settingsQuery.data]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      settingsService.saveSettings({
        general: {
          workspaceName: values.workspaceName,
          supportEmail: values.supportEmail,
          autoReplyEnabled: values.autoReplyEnabled,
          responseSlaSeconds: values.responseSlaSeconds,
        },
        escalation: {
          confidenceThreshold: values.confidenceThreshold,
          autoConnectEnabled: values.autoConnectEnabled,
          defaultQueue: values.defaultQueue,
        },
        integrations: {
          bitrixWebhook: values.bitrixWebhook,
          redmineMailbox: values.redmineMailbox,
          syncEmailCases: values.syncEmailCases,
        },
        models: {
          generationModel: values.generationModel,
          embeddingsModel: values.embeddingsModel,
          visionEnabled: values.visionEnabled,
        },
      }),
    onSuccess: () =>
      toast({
        title: "Настройки сохранены",
        description: "Конфигурация AI-агента обновлена.",
      }),
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
        description="UI уже переведён на живой backend, но сервер пока не отдает конфигурацию этого раздела."
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
          Управление SLA, порогом уверенности, интеграциями и моделями.
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit}>
            <Tabs defaultValue="general">
              <TabsList>
                <TabsTrigger value="general">Общие</TabsTrigger>
                <TabsTrigger value="escalation">Эскалация</TabsTrigger>
                <TabsTrigger value="integrations">Интеграции</TabsTrigger>
                <TabsTrigger value="models">Модели</TabsTrigger>
              </TabsList>
              <TabsContent value="general">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>Название контура</Label>
                    <Input {...form.register("workspaceName")} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Email поддержки</Label>
                    <Input {...form.register("supportEmail")} />
                  </div>
                  <div className="grid gap-2">
                    <Label>SLA ответа, сек</Label>
                    <Input
                      type="number"
                      {...form.register("responseSlaSeconds", { valueAsNumber: true })}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border p-4">
                    <div>
                      <p className="font-medium text-secondary">Автоответы включены</p>
                      <p className="text-sm text-slate-500">
                        Разрешить автоматическую отправку ответов.
                      </p>
                    </div>
                    <Controller
                      control={form.control}
                      name="autoReplyEnabled"
                      render={({ field }) => (
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      )}
                    />
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="escalation">
                <div className="space-y-6">
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
                      name="confidenceThreshold"
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
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="grid gap-2">
                      <Label>Очередь операторов</Label>
                      <Input {...form.register("defaultQueue")} />
                    </div>
                    <div className="flex items-center justify-between rounded-xl border border-border p-4">
                      <div>
                        <p className="font-medium text-secondary">
                          Автоподключение к диалогам
                        </p>
                        <p className="text-sm text-slate-500">
                          Черновики будут подставляться оператору в реальном времени.
                        </p>
                      </div>
                      <Controller
                        control={form.control}
                        name="autoConnectEnabled"
                        render={({ field }) => (
                          <Switch checked={field.value} onCheckedChange={field.onChange} />
                        )}
                      />
                    </div>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="integrations">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>Bitrix24 webhook</Label>
                    <Input {...form.register("bitrixWebhook")} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Redmine mailbox</Label>
                    <Input {...form.register("redmineMailbox")} />
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border p-4 md:col-span-2">
                    <div>
                      <p className="font-medium text-secondary">Синхронизация email-кейсов</p>
                      <p className="text-sm text-slate-500">
                        Письма автоматически попадают в общий журнал обращений.
                      </p>
                    </div>
                    <Controller
                      control={form.control}
                      name="syncEmailCases"
                      render={({ field }) => (
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      )}
                    />
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="models">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label>Generation model</Label>
                    <Input {...form.register("generationModel")} />
                  </div>
                  <div className="grid gap-2">
                    <Label>Embeddings model</Label>
                    <Input {...form.register("embeddingsModel")} />
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-border p-4 md:col-span-2">
                    <div>
                      <p className="font-medium text-secondary">Vision-анализ включён</p>
                      <p className="text-sm text-slate-500">
                        Разрешить анализ PNG и JPEG скриншотов 1С.
                      </p>
                    </div>
                    <Controller
                      control={form.control}
                      name="visionEnabled"
                      render={({ field }) => (
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      )}
                    />
                  </div>
                </div>
              </TabsContent>
            </Tabs>
            <div className="mt-6 flex justify-end">
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
