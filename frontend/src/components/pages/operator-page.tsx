"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { MessageBubble } from "@/src/components/common/message-bubble";
import { OperatorAssistPanel } from "@/src/components/common/operator-assist-panel";
import { Badge } from "@/src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Spinner } from "@/src/components/ui/spinner";
import { Textarea } from "@/src/components/ui/textarea";
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
import { chatService } from "@/src/services/chat-service";

export function OperatorPage({ installationId }: { installationId: string }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reply, setReply] = useState("");

  const ticketsQuery = useQuery({
    queryKey: ["conversations", installationId, 1],
    queryFn: () => chatService.listConversations(installationId, 1, 50, "escalated"),
    refetchInterval: 5_000,
  });
  const tickets = ticketsQuery.data?.items ?? [];
  const activeTicketId =
    selectedId && tickets.some((ticket) => ticket.id === selectedId)
      ? selectedId
      : (tickets[0]?.id ?? null);

  const conversationQuery = useQuery({
    queryKey: ["conversation", installationId, activeTicketId],
    queryFn: () => chatService.getConversation(activeTicketId ?? "", installationId),
    enabled: Boolean(activeTicketId),
    refetchInterval: 5_000,
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["conversations"] });
    await queryClient.invalidateQueries({
      queryKey: ["conversation", installationId, activeTicketId],
    });
  };

  const generateMutation = useMutation({
    mutationFn: () =>
      chatService.generateSuggestion(activeTicketId ?? "", installationId),
    onSuccess: async () => {
      await invalidate();
    },
    onError: (error) =>
      toast({
        title: "Не удалось сгенерировать ответ",
        description: error instanceof Error ? error.message : undefined,
        variant: "destructive",
      }),
  });

  const resolveMutation = useMutation({
    mutationFn: () =>
      chatService.resolveConversation(activeTicketId ?? "", installationId),
    onSuccess: async () => {
      setSelectedId(null);
      setReply("");
      await invalidate();
      toast({ title: "Диалог закрыт" });
    },
    onError: (error) =>
      toast({
        title: "Не удалось закрыть диалог",
        description: error instanceof Error ? error.message : undefined,
        variant: "destructive",
      }),
  });

  const sendMutation = useMutation({
    mutationFn: () => {
      const text =
        reply.trim() || conversationQuery.data?.suggestedResponse?.trim() || "";
      return chatService.sendOperatorReply(activeTicketId ?? "", installationId, text);
    },
    onSuccess: async () => {
      setReply("");
      await invalidate();
      toast({ title: "Ответ отправлен" });
    },
    onError: (error) =>
      toast({
        title: "Не удалось отправить",
        description: error instanceof Error ? error.message : undefined,
        variant: "destructive",
      }),
  });

  if (ticketsQuery.isLoading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (ticketsQuery.isError) {
    return (
      <ApiStateCard
        title="Операторская недоступна"
        description="Не удалось загрузить эскалированные диалоги."
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
          Активные эскалации. Черновик считается только по кнопке — не на каждое сообщение гостя.
        </p>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle>Активные тикеты</CardTitle>
          </CardHeader>
          <CardContent>
            {tickets.length === 0 ? (
              <p className="text-sm text-slate-500">Нет эскалированных диалогов.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Тикет</TableHead>
                    <TableHead>Статус</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tickets.map((ticket) => (
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
                          <p className="font-medium text-secondary">{ticket.userId}</p>
                          <p className="text-xs text-slate-400">
                            {formatDateTime(ticket.createdAt)}
                          </p>
                        </button>
                      </TableCell>
                      <TableCell>
                        <Badge>{ticket.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
        <Card className="h-[calc(100vh-14rem)]">
          <CardHeader>
            <CardTitle>Диалог</CardTitle>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-5rem)] flex-col p-0">
            <ScrollArea className="flex-1">
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
            {conversationQuery.data ? (
              <div className="border-t border-border p-4">
                <Textarea
                  rows={3}
                  placeholder="Правка ответа оператора"
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                />
              </div>
            ) : null}
          </CardContent>
        </Card>
        {conversationQuery.data ? (
          <OperatorAssistPanel
            conversation={conversationQuery.data}
            generatePending={generateMutation.isPending}
            resolvePending={resolveMutation.isPending}
            canSend={Boolean(
              reply.trim() || conversationQuery.data?.suggestedResponse?.trim(),
            )}
            sendPending={sendMutation.isPending}
            onGenerateDraft={() => generateMutation.mutate()}
            onSendDraft={() => sendMutation.mutate()}
            onEditDraft={() =>
              setReply((current) => current || conversationQuery.data?.suggestedResponse || "")
            }
            onResolve={() => resolveMutation.mutate()}
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
