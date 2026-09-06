"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  MessageSquareWarning,
  Percent,
  Timer,
} from "lucide-react";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { StatsCard } from "@/src/components/common/stats-card";
import { DatePicker } from "@/src/components/ui/date-picker";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Spinner } from "@/src/components/ui/spinner";
import { analyticsService } from "@/src/services/analytics-service";

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatSeconds(value: number): string {
  if (value < 10) {
    return `${value.toFixed(1)} с`;
  }
  return `${Math.round(value)} с`;
}

export function AnalyticsPage({ installationId }: { installationId: string }) {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data, error, isLoading } = useQuery({
    queryKey: ["metrics", installationId, dateFrom, dateTo],
    queryFn: () =>
      analyticsService.getMetrics({
        installationId,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
  });

  if (isLoading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (!data) {
    return (
      <ApiStateCard
        title="Аналитика недоступна"
        description="Не удалось получить агрегаты из GET /api/metrics."
        detail={error instanceof Error ? error.message : undefined}
        actionHref="/"
        actionLabel="Вернуться на дашборд"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Аналитика</h1>
        <p className="mt-2 text-slate-500">
          Живые метрики агента из API. Внешний Grafana — перспектива, не часть
          этого экрана.
        </p>
      </div>
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle>Период</CardTitle>
          <div className="flex flex-col gap-3 md:flex-row">
            <DatePicker value={dateFrom} onChange={setDateFrom} />
            <DatePicker value={dateTo} onChange={setDateTo} />
          </div>
        </CardHeader>
        <CardContent className="text-sm text-slate-500">
          Пустые даты — весь доступный период установки. Фильтры уходят в
          `date_from` / `date_to` на `GET /api/metrics`.
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-3">
        <StatsCard
          icon={Percent}
          label="Автоответы"
          value={formatPercent(data.auto_answer_percent)}
          hint="% ответов без эскалации"
        />
        <StatsCard
          icon={Timer}
          label="Среднее время ответа"
          value={formatSeconds(data.avg_response_time_seconds)}
          hint="Секунды до первого ответа агента"
        />
        <StatsCard
          icon={MessageSquareWarning}
          label="Эскалации"
          value={String(data.escalation_count)}
          hint="Число передач оператору"
        />
      </div>
    </div>
  );
}
