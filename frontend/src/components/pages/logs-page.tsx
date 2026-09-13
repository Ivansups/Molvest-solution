"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { DataTablePagination } from "@/src/components/common/data-table-pagination";
import { DatePicker } from "@/src/components/ui/date-picker";
import { Badge } from "@/src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/src/components/ui/select";
import { Spinner } from "@/src/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/src/components/ui/table";
import { logsService } from "@/src/services/logs-service";
import type { LogEventType } from "@/src/types/api";

const PAGE_SIZE = 50;

const EVENT_LABELS: Record<LogEventType, string> = {
  escalation: "Эскалация",
  conversation_resolved: "Диалог закрыт",
  document_indexed: "Документ проиндексирован",
  document_failed: "Ошибка индексации",
};

type EventFilter = LogEventType | "all";

export function LogsPage({ installationId }: { installationId: string }) {
  const [eventType, setEventType] = useState<EventFilter>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["logs", installationId, eventType, dateFrom, dateTo, page],
    queryFn: () =>
      logsService.listEvents({
        installationId,
        eventType,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        page,
        pageSize: PAGE_SIZE,
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
        title="Журнал недоступен"
        description="Не удалось получить события из GET /api/logs."
        detail={error instanceof Error ? error.message : undefined}
        actionHref="/"
        actionLabel="Вернуться на дашборд"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Журнал</h1>
        <p className="mt-2 text-slate-500">
          Эскалации, закрытия диалогов и статусы индексации документов. Время —
          UTC ISO.
        </p>
      </div>
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle>Фильтры</CardTitle>
          <div className="flex flex-col gap-3 md:flex-row">
            <Select
              value={eventType}
              onValueChange={(value) => {
                setPage(1);
                setEventType(value as EventFilter);
              }}
            >
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Тип события" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все типы</SelectItem>
                <SelectItem value="escalation">Эскалация</SelectItem>
                <SelectItem value="conversation_resolved">Диалог закрыт</SelectItem>
                <SelectItem value="document_indexed">
                  Документ проиндексирован
                </SelectItem>
                <SelectItem value="document_failed">Ошибка индексации</SelectItem>
              </SelectContent>
            </Select>
            <DatePicker
              value={dateFrom}
              onChange={(value) => {
                setPage(1);
                setDateFrom(value);
              }}
            />
            <DatePicker
              value={dateTo}
              onChange={(value) => {
                setPage(1);
                setDateTo(value);
              }}
            />
          </div>
        </CardHeader>
        <CardContent className={data.items.length === 0 ? "px-6 pb-8 pt-0" : "p-0"}>
          {data.items.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500">
              Пока нет событий за выбранные фильтры.
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Время (UTC)</TableHead>
                    <TableHead>Тип</TableHead>
                    <TableHead>Диалог / документ</TableHead>
                    <TableHead>Сообщение</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="whitespace-nowrap font-mono text-xs">
                        {item.occurred_at}
                      </TableCell>
                      <TableCell>
                        <Badge>{EVENT_LABELS[item.event_type]}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-slate-600">
                        {item.conversation_id ?? item.document_id ?? "—"}
                      </TableCell>
                      <TableCell>{item.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <DataTablePagination
                page={data.page}
                pageSize={data.page_size}
                total={data.total}
                onPageChange={setPage}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
