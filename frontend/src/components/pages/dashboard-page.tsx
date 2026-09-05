import {
  CheckCircle2,
  Clock3,
  MessageSquareMore,
  TriangleAlert,
} from "lucide-react";
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
import type {
  ConversationListOut,
  ConversationMetrics,
  DocumentListOut,
} from "@/src/types/api";

export function DashboardPage({
  health,
  documents,
  conversations,
  metrics,
}: {
  health: ServerResult<{ status: string }>;
  documents: ServerResult<DocumentListOut>;
  conversations: ServerResult<ConversationListOut>;
  metrics: ServerResult<ConversationMetrics>;
}) {
  const items = documents.ok ? documents.data.items : [];
  const indexedCount = items.filter((item) => item.status === "INDEXED").length;
  const pendingCount = items.filter((item) => item.status === "PENDING").length;
  const failedCount = items.filter((item) => item.status === "FAILED").length;
  const [latestUpload] = [...items].sort(
    (left, right) =>
      new Date(right.uploaded_at).getTime() - new Date(left.uploaded_at).getTime(),
  );
  const lastUpload = latestUpload?.uploaded_at ?? null;
  const conversationItems = conversations.ok ? conversations.data.items : [];
  const conversationTotal = conversations.ok ? conversations.data.total : 0;
  const conversationMetrics = metrics.ok ? metrics.data : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Дашборд</h1>
        <p className="mt-2 text-slate-500">
          Обращения, автоответы и эскалации из API этапа 6.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-4">
        <StatsCard
          icon={MessageSquareMore}
          label="Всего обращений"
          value={String(conversationTotal)}
          hint="Диалоги в текущей установке"
        />
        <StatsCard
          icon={CheckCircle2}
          label="Автоответы"
          value={conversationMetrics ? `${conversationMetrics.auto_answer_percent}%` : "--"}
          hint="Доля обращений без эскалации"
        />
        <StatsCard
          icon={Clock3}
          label="Среднее время ответа"
          value={conversationMetrics ? `${conversationMetrics.avg_response_time_seconds} сек` : "--"}
          hint="Первый ответ в диалоге"
        />
        <StatsCard
          icon={TriangleAlert}
          label="Эскалации"
          value={conversationMetrics ? String(conversationMetrics.escalation_count) : "--"}
          hint="Передано оператору"
        />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Последние чаты</CardTitle>
          </CardHeader>
          <CardContent>
            {!conversations.ok ? (
              <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4 text-sm leading-6 text-slate-500">
                {conversations.message}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Пользователь</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Создан</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {conversationItems.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.user_id}</TableCell>
                      <TableCell>
                        <Badge
                          className={
                            item.status === "escalated"
                              ? "border-warning/30 bg-warning/10 text-warning"
                              : undefined
                          }
                        >
                          {item.status === "escalated" ? "Эскалация" : item.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatDateTime(item.created_at)}</TableCell>
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
                  <p className="text-sm font-medium text-secondary">`GET /api/metrics`</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Метрики обращений этапа 6
                  </p>
                </div>
                <Badge
                  className={
                    metrics.ok
                      ? "border-primary/20 bg-primary/10 text-primary"
                      : "border-destructive/20 bg-destructive/10 text-destructive"
                  }
                >
                  {metrics.ok ? "connected" : "offline"}
                </Badge>
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">`GET /api/conversations`</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Список обращений для дашборда и оператора
                  </p>
                </div>
                <Badge
                  className={
                    conversations.ok
                      ? "border-primary/20 bg-primary/10 text-primary"
                      : "border-destructive/20 bg-destructive/10 text-destructive"
                  }
                >
                  {conversations.ok ? "connected" : "offline"}
                </Badge>
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">Документы базы знаний</p>
                  <p className="mt-1 text-sm text-slate-500">
                    {lastUpload ? `Последняя загрузка: ${formatDateTime(lastUpload)}` : "Документы ещё не загружались"}
                  </p>
                </div>
                <Clock3 className="h-4 w-4 text-slate-400" />
              </div>
            </div>
            <div className="rounded-[22px] border border-border/70 bg-slate-50/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-secondary">Индексация</p>
                  <p className="mt-1 text-sm text-slate-500">
                    INDEXED: {indexedCount}, PENDING: {pendingCount}, FAILED: {failedCount}
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
