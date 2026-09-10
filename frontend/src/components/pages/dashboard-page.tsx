import {
  CheckCircle2,
  Clock3,
  FileClock,
  Files,
  MessageSquareWarning,
  Percent,
  ShieldCheck,
  Timer,
} from "lucide-react";
import { DocumentStatusBadge } from "@/src/components/common/document-status-badge";
import { StatsCard } from "@/src/components/common/stats-card";
import { Badge } from "@/src/components/ui/badge";
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
import type { ServerResult } from "@/src/lib/server-api";
import type { ConversationMetrics, DocumentListOut } from "@/src/types/api";

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatSeconds(value: number): string {
  if (value < 10) {
    return `${value.toFixed(1)} с`;
  }
  return `${Math.round(value)} с`;
}

export function DashboardPage({
  health,
  documents,
  metrics,
}: {
  health: ServerResult<{ status: string }>;
  documents: ServerResult<DocumentListOut>;
  metrics: ServerResult<ConversationMetrics>;
}) {
  const items = documents.ok ? documents.data.items : [];
  const total = documents.ok ? documents.data.total : items.length;
  const indexedCount = items.filter((item) => item.status === "INDEXED").length;
  const pendingCount = items.filter((item) => item.status === "PENDING").length;
  const failedCount = items.filter((item) => item.status === "FAILED").length;
  const [latestUpload] = [...items].sort(
    (left, right) =>
      new Date(right.uploaded_at).getTime() - new Date(left.uploaded_at).getTime(),
  );
  const lastUpload = latestUpload?.uploaded_at ?? null;
  const healthOk = health.ok && health.data.status === "ok";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Дашборд</h1>
        <p className="mt-2 text-slate-500">
          Статус API, база знаний и эффективность агента по живым метрикам.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-4">
        <StatsCard
          icon={ShieldCheck}
          label="Статус API"
          value={healthOk ? "ONLINE" : "OFFLINE"}
          hint={health.ok ? "Проверка через /health" : "Backend недоступен"}
        />
        <StatsCard
          icon={Files}
          label="Документы"
          value={String(total)}
          hint="Всего записей в базе знаний"
        />
        <StatsCard
          icon={CheckCircle2}
          label="Индексировано"
          value={String(indexedCount)}
          hint="Документы со статусом INDEXED"
        />
        <StatsCard
          icon={FileClock}
          label="Ожидают / failed"
          value={`${pendingCount} / ${failedCount}`}
          hint="Статусы PENDING и FAILED"
        />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {metrics.ok ? (
          <>
            <StatsCard
              icon={Percent}
              label="Автоответы"
              value={formatPercent(metrics.data.auto_answer_percent)}
              hint="Доля ответов без эскалации (GET /api/metrics)"
            />
            <StatsCard
              icon={Timer}
              label="Среднее время ответа"
              value={formatSeconds(metrics.data.avg_response_time_seconds)}
              hint="От первого сообщения пользователя до первого ответа"
            />
            <StatsCard
              icon={MessageSquareWarning}
              label="Эскалации"
              value={String(metrics.data.escalation_count)}
              hint="Число передач оператору за период"
            />
          </>
        ) : (
          <Card className="md:col-span-3">
            <CardHeader>
              <CardTitle>Метрики агента</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
                {metrics.message}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Документы базы знаний</CardTitle>
          </CardHeader>
          <CardContent>
            {!documents.ok ? (
              <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
                {documents.message}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead>Тип</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Загружен</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.title}</TableCell>
                      <TableCell>{item.file_type}</TableCell>
                      <TableCell>
                        <DocumentStatusBadge status={item.status} />
                      </TableCell>
                      <TableCell>{formatDateTime(item.uploaded_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Контур backend</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">`GET /health`</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Проверка доступности FastAPI
                  </p>
                </div>
                <Badge
                  className={
                    healthOk
                      ? "border-primary/20 bg-primary/10 text-primary"
                      : "border-destructive/20 bg-destructive/10 text-destructive"
                  }
                >
                  {health.ok ? health.data.status : "offline"}
                </Badge>
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">`GET /api/metrics`</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Источник цифр эффективности агента
                  </p>
                </div>
                <Badge
                  className={
                    metrics.ok
                      ? "border-primary/20 bg-primary/10 text-primary"
                      : "border-destructive/20 bg-destructive/10 text-destructive"
                  }
                >
                  {metrics.ok ? "live" : "offline"}
                </Badge>
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">Последняя загрузка</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {lastUpload
                      ? formatDateTime(lastUpload)
                      : "Документы ещё не загружались"}
                  </p>
                </div>
                <Clock3 className="h-4 w-4 text-slate-400" />
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">Ошибки загрузки</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Документы со статусом FAILED требуют повторной проверки
                  </p>
                </div>
                <Badge
                  className={
                    failedCount > 0
                      ? "border-warning/30 bg-warning/10 text-warning"
                      : "border-primary/20 bg-primary/10 text-primary"
                  }
                >
                  {failedCount}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
      {!health.ok ? (
        <Card>
          <CardHeader>
            <CardTitle>Статус подключения</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-[22px] border border-destructive/20 bg-destructive/5 p-4 text-sm leading-6 text-foreground">
              {health.message}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
