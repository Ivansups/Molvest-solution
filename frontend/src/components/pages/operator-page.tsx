"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { MessageBubble } from "@/src/components/common/message-bubble";
import { OperatorAssistPanel } from "@/src/components/common/operator-assist-panel";
import { Badge } from "@/src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Spinner } from "@/src/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/src/components/ui/table";
import { useToast } from "@/src/hooks/use-toast";
import { formatDateTime } from "@/src/lib/format";
import { analyticsService } from "@/src/services/analytics-service";
import { chatService } from "@/src/services/chat-service";

export function OperatorPage() {
  const { toast } = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const ticketsQuery = useQuery({
    queryKey: ["operator-tickets"],
    queryFn: () => analyticsService.getActiveTickets(),
  });
  const activeTicketId = selectedId ?? ticketsQuery.data?.[0]?.id ?? null;

  const conversationQuery = useQuery({
    queryKey: ["operator-conversation", activeTicketId],
    queryFn: () => chatService.getConversation(activeTicketId ?? ""),
    enabled: Boolean(activeTicketId),
  });

  if (ticketsQuery.isLoading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (!ticketsQuery.data) {
    return (
      <ApiStateCard
        title="Операторская недоступна"
        description="Раздел подключён к backend, но сервер пока не публикует активные эскалации."
        detail={ticketsQuery.error instanceof Error ? ticketsQuery.error.message : undefined}
        actionHref="/chat"
        actionLabel="Открыть публичный чат"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-secondary">Операторская</h1>
        <p className="mt-2 text-slate-500">
          Активные эскалации и черновики ответов для операторов поддержки.
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Активные тикеты</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Тикет</TableHead>
                  <TableHead>Канал</TableHead>
                  <TableHead>Приоритет</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ticketsQuery.data.map((ticket) => (
                  <TableRow
                    key={ticket.id}
                    className={ticket.id === activeTicketId ? "bg-slate-50" : ""}
                  >
                    <TableCell>
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => setSelectedId(ticket.id)}
                      >
                        <p className="font-medium text-secondary">{ticket.subject}</p>
                        <p className="text-sm text-slate-500">{ticket.userName}</p>
                        <p className="text-xs text-slate-400">
                          {formatDateTime(ticket.escalatedAt)}
                        </p>
                      </button>
                    </TableCell>
                    <TableCell>{ticket.channel}</TableCell>
                    <TableCell>
                      <Badge>{ticket.priority}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card className="h-[calc(100vh-14rem)]">
          <CardHeader>
            <CardTitle>Диалог</CardTitle>
          </CardHeader>
          <CardContent className="h-[calc(100%-5rem)] p-0">
            <ScrollArea className="h-full">
              <div className="space-y-4 p-6">
                {conversationQuery.isLoading ? (
                  <div className="flex h-64 items-center justify-center">
                    <Spinner className="h-6 w-6" />
                  </div>
                ) : null}
                {conversationQuery.data?.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
        {conversationQuery.data ? (
          <OperatorAssistPanel
            conversation={conversationQuery.data}
            onSendDraft={() =>
              toast({
                title: "Ответ отправлен",
                description: "Пользователь получил ответ оператора.",
              })
            }
            onEditDraft={() =>
              toast({
                title: "Черновик открыт",
                description: "Заполните сообщение в основном окне чата.",
              })
            }
          />
        ) : (
          <Card>
            <CardContent className="flex h-full items-center justify-center text-slate-500">
              Нет выбранного тикета
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
