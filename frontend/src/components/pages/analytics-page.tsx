"use client";

import { Clock3, MessageSquareMore, TriangleAlert } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { StatsCard } from "@/src/components/common/stats-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import type { ServerResult } from "@/src/lib/server-api";
import type { ConversationMetrics } from "@/src/types/api";

const PIE_COLORS = ["#00A650", "#E3A008"];

type Trend = {
  date: string;
  tickets: number;
  autoReplies: number;
  escalations: number;
};

export function AnalyticsPage({
  metrics,
  trends,
}: {
  metrics: ServerResult<ConversationMetrics>;
  trends: Trend[];
}) {
  if (!metrics.ok) {
    return (
      <ApiStateCard
        title="Аналитика недоступна"
        description="Не удалось получить данные из API метрик."
        detail={metrics.message}
        actionHref="/"
        actionLabel="Вернуться на дашборд"
      />
    );
  }

  const distribution = [
    { name: "Автоответы", value: metrics.data.auto_answer_percent },
    { name: "Эскалации", value: 100 - metrics.data.auto_answer_percent },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Аналитика</h1>
        <p className="mt-2 text-slate-500">
          Динамика за последние 7 дней и показатели из `GET /api/metrics`.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <StatsCard
          icon={MessageSquareMore}
          label="Автоответы"
          value={`${metrics.data.auto_answer_percent}%`}
          hint="Доля обращений без эскалации"
        />
        <StatsCard
          icon={Clock3}
          label="Среднее время ответа"
          value={`${metrics.data.avg_response_time_seconds} сек`}
          hint="Первый ответ в диалоге"
        />
        <StatsCard
          icon={TriangleAlert}
          label="Эскалации"
          value={String(metrics.data.escalation_count)}
          hint="За весь доступный период"
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <Card>
          <CardHeader>
            <CardTitle>Обращения по дням</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends}>
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="tickets" name="Обращения" fill="#1A3B6B" />
                <Bar dataKey="autoReplies" name="Автоответы" fill="#00A650" />
                <Bar dataKey="escalations" name="Эскалации" fill="#E3A008" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Автоответы и эскалации</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distribution}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={70}
                  outerRadius={110}
                >
                  {distribution.map((entry, index) => (
                    <Cell key={entry.name} fill={PIE_COLORS[index]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
