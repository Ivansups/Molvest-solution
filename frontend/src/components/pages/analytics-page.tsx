"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { DatePicker } from "@/src/components/ui/date-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/src/components/ui/select";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { analyticsService } from "@/src/services/analytics-service";
import { Spinner } from "@/src/components/ui/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/src/components/ui/table";
import { formatDateTime } from "@/src/lib/format";

const pieColors = ["#00A650", "#1A3B6B"];

export function AnalyticsPage() {
  const [dateFrom, setDateFrom] = useState("2026-08-26");
  const [dateTo, setDateTo] = useState("2026-09-01");
  const [eventType, setEventType] = useState("all");

  const { data, error, isLoading } = useQuery({
    queryKey: ["analytics"],
    queryFn: () => analyticsService.getAnalytics(),
  });

  const filteredLogs = useMemo(() => {
    if (!data) {
      return [];
    }

    return data.logs.filter((item) => {
      const eventDate = item.createdAt.slice(0, 10);
      const withinRange = eventDate >= dateFrom && eventDate <= dateTo;
      const matchesType = eventType === "all" || item.type === eventType;
      return withinRange && matchesType;
    });
  }, [data, dateFrom, dateTo, eventType]);

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
        description="Раздел подключён к backend, но нужный endpoint ещё не опубликован."
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
          Метрики загрузки, эффективности автоответов и журнал событий.
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <Card>
          <CardHeader>
            <CardTitle>Обращения по дням</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.trends}>
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="tickets" fill="#1A3B6B" radius={[8, 8, 0, 0]} />
                <Bar dataKey="autoReplies" fill="#00A650" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Автоответы vs эскалации</CardTitle>
          </CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.distribution}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={70}
                  outerRadius={110}
                >
                  {data.distribution.map((entry, index) => (
                    <Cell key={entry.name} fill={pieColors[index]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle>Логи</CardTitle>
          <div className="flex flex-col gap-3 md:flex-row">
            <DatePicker value={dateFrom} onChange={setDateFrom} />
            <DatePicker value={dateTo} onChange={setDateTo} />
            <Select value={eventType} onValueChange={setEventType}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Тип события" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все</SelectItem>
                <SelectItem value="chat">Chat</SelectItem>
                <SelectItem value="kb">Knowledge base</SelectItem>
                <SelectItem value="operator">Operator</SelectItem>
                <SelectItem value="system">System</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Дата</TableHead>
                <TableHead>Тип</TableHead>
                <TableHead>Событие</TableHead>
                <TableHead>Инициатор</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell>{formatDateTime(log.createdAt)}</TableCell>
                  <TableCell>{log.type}</TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium text-secondary">{log.title}</p>
                      <p className="text-sm text-slate-500">{log.description}</p>
                    </div>
                  </TableCell>
                  <TableCell>{log.actor}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
