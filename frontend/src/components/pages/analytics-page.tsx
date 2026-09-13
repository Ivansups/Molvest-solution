"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale";
import {
  MessageSquareWarning,
  Percent,
  Timer,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { StatsCard } from "@/src/components/common/stats-card";
import { DatePicker } from "@/src/components/ui/date-picker";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Spinner } from "@/src/components/ui/spinner";
import { analyticsService } from "@/src/services/analytics-service";
import type { ConversationMetrics } from "@/src/types/api";

const AUTO_COLOR = "var(--primary)";
const ESCALATION_COLOR = "var(--secondary)";
const CONVERSATION_COLOR = "var(--secondary)";
const ESCALATION_BAR_COLOR = "var(--warning)";

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatSeconds(value: number): string {
  if (value < 10) {
    return `${value.toFixed(1)} с`;
  }
  return `${Math.round(value)} с`;
}

function formatDayTick(value: string): string {
  return format(parseISO(value), "dd.MM", { locale: ru });
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
        description="Не удалось получить показатели поддержки. Попробуйте обновить страницу позже."
        detail={error instanceof Error ? error.message : undefined}
        actionHref="/"
        actionLabel="Вернуться на рабочий стол"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Аналитика качества</h1>
        <p className="mt-2 text-slate-500">
          Автоответы, скорость реакции и передачи оператору по выбранному периоду.
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
          Оставьте даты пустыми, чтобы увидеть весь доступный период установки.
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
      <div className="grid gap-4 xl:grid-cols-2">
        <ShareChart data={data} />
        <DailyChart data={data} />
      </div>
    </div>
  );
}

function ChartEmpty({ text }: { text: string }) {
  return (
    <div className="flex h-[280px] items-center justify-center text-sm text-slate-500">
      {text}
    </div>
  );
}

function ShareChart({ data }: { data: ConversationMetrics }) {
  const escalatedAnswers = Math.max(data.answer_count - data.auto_answer_count, 0);
  const shareData = [
    { name: "Автоответы", value: data.auto_answer_count, color: AUTO_COLOR },
    { name: "С эскалацией", value: escalatedAnswers, color: ESCALATION_COLOR },
  ].filter((item) => item.value > 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Автоответы и эскалации</CardTitle>
        <p className="text-sm text-slate-500">
          Доля ответов агента без передачи оператору.
        </p>
      </CardHeader>
      <CardContent>
        {data.answer_count === 0 ? (
          <ChartEmpty text="Пока нет ответов агента за выбранный период." />
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={shareData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={62}
                  outerRadius={92}
                  paddingAngle={shareData.length > 1 ? 3 : 0}
                  stroke="none"
                >
                  {shareData.map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "rgba(251,255,252,0.96)",
                    border: "1px solid var(--border)",
                    borderRadius: "16px",
                    color: "var(--foreground)",
                  }}
                  formatter={(value) => [
                    `${Number(value)} · ${formatPercent(
                      data.answer_count
                        ? (Number(value) / data.answer_count) * 100
                        : 0,
                    )}`,
                    "",
                  ]}
                />
                <Legend
                  formatter={(value) => (
                    <span className="text-sm text-slate-600">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DailyChart({ data }: { data: ConversationMetrics }) {
  const daily = data.daily.map((point) => ({
    ...point,
    label: formatDayTick(point.date),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Диалоги по дням</CardTitle>
        <p className="text-sm text-slate-500">
          Число диалогов и передач оператору за период.
        </p>
      </CardHeader>
      <CardContent>
        {daily.length === 0 ? (
          <ChartEmpty text="Пока нет диалогов за выбранный период." />
        ) : (
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "var(--muted)", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <Tooltip
                  contentStyle={{
                    background: "rgba(251,255,252,0.96)",
                    border: "1px solid var(--border)",
                    borderRadius: "16px",
                    color: "var(--foreground)",
                  }}
                  formatter={(value, name) => [
                    Number(value),
                    name === "conversation_count" ? "Диалоги" : "Эскалации",
                  ]}
                  labelFormatter={(_, payload) => {
                    const point = payload?.[0]?.payload as
                      | { date?: string }
                      | undefined;
                    return point?.date
                      ? format(parseISO(point.date), "d MMMM yyyy", { locale: ru })
                      : "";
                  }}
                />
                <Legend
                  formatter={(value) => (
                    <span className="text-sm text-slate-600">
                      {value === "conversation_count" ? "Диалоги" : "Эскалации"}
                    </span>
                  )}
                />
                <Bar
                  dataKey="conversation_count"
                  fill={CONVERSATION_COLOR}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={28}
                />
                <Bar
                  dataKey="escalation_count"
                  fill={ESCALATION_BAR_COLOR}
                  radius={[6, 6, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
