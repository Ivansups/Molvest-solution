"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ellipsis,
  ImagePlus,
  Send,
  ShieldAlert,
} from "lucide-react";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { FileDropzone } from "@/src/components/common/file-dropzone";
import { MessageBubble } from "@/src/components/common/message-bubble";
import { OperatorAssistPanel } from "@/src/components/common/operator-assist-panel";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/src/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/src/components/ui/dropdown-menu";
import { ScrollArea } from "@/src/components/ui/scroll-area";
import { Separator } from "@/src/components/ui/separator";
import { Spinner } from "@/src/components/ui/spinner";
import { Textarea } from "@/src/components/ui/textarea";
import type { ConversationMessage, UserSession } from "@/src/types/domain";
import { useToast } from "@/src/hooks/use-toast";
import { formatDateTime } from "@/src/lib/format";
import { chatService } from "@/src/services/chat-service";

async function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
    reader.readAsDataURL(file);
  });
}

export function ChatPage({
  detailMode = false,
  mode,
  user = null,
}: {
  detailMode?: boolean;
  mode: "guest" | "support";
  user?: UserSession | null;
}) {
  const params = useParams<{ ticketId: string }>();
  const ticketId = params.ticketId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [draft, setDraft] = useState("");
  const [guestConversationId, setGuestConversationId] = useState<string | null>(null);
  const [guestMessages, setGuestMessages] = useState<ConversationMessage[]>([]);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const [pendingImage, setPendingImage] = useState<{
    name: string;
    previewUrl: string;
    base64: string;
  } | null>(null);

  const isSupportMode = mode === "support";

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => chatService.listConversations(),
    enabled: isSupportMode,
  });

  const selectedId = isSupportMode
    ? ticketId ?? conversationsQuery.data?.[0]?.id ?? null
    : guestConversationId;

  useEffect(() => {
    if (isSupportMode && !ticketId && conversationsQuery.data?.[0]?.id) {
      router.replace(`/chat/support/${conversationsQuery.data[0].id}`);
    }
  }, [conversationsQuery.data, isSupportMode, router, ticketId]);

  const conversationQuery = useQuery({
    queryKey: ["conversation", selectedId],
    queryFn: () => chatService.getConversation(selectedId ?? ""),
    enabled: isSupportMode && Boolean(selectedId),
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      if (!draft.trim() && !pendingImage) {
        return null;
      }

      const guestUserId = `guest-${guestConversationId ?? "session"}`;
      const workspaceId = user?.installationId ?? "guest-workspace-molvest";

      return chatService.sendMessage(
        {
          message_id: crypto.randomUUID(),
          workspace_id: workspaceId,
          conversation_id: selectedId,
          text: draft.trim() || null,
          image_base64: pendingImage?.base64.split(",")[1] ?? null,
          user_id: user?.id ?? guestUserId,
        },
      );
    },
    onSuccess: async (data) => {
      if (!data) {
        return;
      }

      const createdAt = new Date().toISOString();
      if (!isSupportMode) {
        const userContent = draft.trim() || "Пользователь отправил изображение";
        const nextGuestMessages: ConversationMessage[] = [
          ...guestMessages,
          {
            id: crypto.randomUUID(),
            role: "user",
            content: userContent,
            createdAt,
            imageUrl: pendingImage?.previewUrl,
          },
          {
            id: data.message_id,
            role: data.escalated ? "system" : "assistant",
            content: data.text,
            createdAt,
            confidence: data.confidence,
            escalated: data.escalated,
            sources: data.sources,
          },
        ];
        setGuestConversationId(data.conversation_id);
        setGuestMessages(nextGuestMessages);
      }

      setDraft("");
      setPendingImage(null);
      if (isSupportMode) {
        await queryClient.invalidateQueries({ queryKey: ["conversations"] });
        await queryClient.invalidateQueries({ queryKey: ["conversation", selectedId] });
      }
      toast({
        title: data.escalated ? "Диалог эскалирован" : "Сообщение отправлено",
        description: data.text,
      });
    },
    onError: (error) =>
      toast({
        title: "Backend не ответил",
        description: error instanceof Error ? error.message : "Повторите запрос позже.",
        variant: "destructive",
      }),
  });

  const conversation = conversationQuery.data;

  if (!isSupportMode) {
    return (
      <>
        <Card className="shell-panel overflow-hidden rounded-[30px]">
          <CardContent className="grid gap-0 p-0 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-h-[640px] flex-col">
              <div className="border-b border-border/60 px-6 py-5">
                <p className="text-[11px] uppercase tracking-[0.2em] text-primary">
                  Новый диалог
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-secondary">
                  Гостевой чат поддержки 1С
                </h2>
              </div>
              <ScrollArea className="flex-1">
                <div className="space-y-4 p-6">
                  {guestMessages.length === 0 ? (
                    <div className="rounded-[26px] border border-dashed border-border bg-slate-50/80 p-6">
                      <p className="text-base font-medium text-secondary">
                        Опишите проблему, код ошибки, форму 1С или приложите скриншот.
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-500">
                        Чем точнее контекст обращения, тем релевантнее подбор источников
                        и итоговый ответ.
                      </p>
                    </div>
                  ) : null}
                  {guestMessages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
                </div>
              </ScrollArea>
              <Separator />
              <div className="space-y-4 p-6">
                {pendingImage ? (
                  <div className="rounded-xl border border-border bg-slate-50 p-3">
                    <p className="text-sm font-medium text-secondary">{pendingImage.name}</p>
                    <Image
                      src={pendingImage.previewUrl}
                      alt={pendingImage.name}
                      width={640}
                      height={360}
                      unoptimized
                      className="mt-3 max-h-40 rounded-2xl border border-border"
                    />
                  </div>
                ) : null}
                <Textarea
                  rows={5}
                  placeholder="Опишите ошибку, код 1С или приложите скриншот"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Button variant="outline" onClick={() => setImageDialogOpen(true)}>
                    <ImagePlus className="h-4 w-4" />
                    Прикрепить скриншот
                  </Button>
                  <Button
                    onClick={() => sendMutation.mutate()}
                    disabled={sendMutation.isPending}
                  >
                    <Send className="h-4 w-4" />
                    Отправить вопрос
                  </Button>
                </div>
              </div>
            </div>
            <div className="border-t border-border/60 bg-slate-50/70 p-6 xl:border-l xl:border-t-0">
              <div className="space-y-4">
                <div className="rounded-[24px] bg-white/92 p-5 shadow-[0_10px_24px_rgba(27,51,85,0.05)]">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-primary">
                    Контекст обращения
                  </p>
                  <div className="mt-4 space-y-3">
                    <div className="rounded-[20px] border border-border/70 bg-slate-50/80 p-4">
                      <p className="text-sm font-medium text-secondary">
                        Что указать в сообщении
                      </p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        Код ошибки, название формы 1С и действие перед сбоем.
                      </p>
                    </div>
                    <div className="rounded-[20px] border border-border/70 bg-slate-50/80 p-4">
                      <p className="text-sm font-medium text-secondary">Скриншоты</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        PNG и JPEG добавляются к сообщению и доступны для анализа.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-[24px] border border-secondary/12 bg-secondary p-5 text-white">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-white/60">
                    Закрытая панель
                  </p>
                  <p className="mt-3 text-sm leading-6 text-white/76">
                    Сотрудники поддержки работают отдельно: документы, эскалации и
                    операторский поток доступны только после авторизации.
                  </p>
                  <Button
                    variant="outline"
                    className="mt-4 w-full border-white/16 !bg-white !text-secondary hover:!bg-white/92"
                    asChild
                  >
                    <Link href="/login">Открыть вход для поддержки</Link>
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Dialog open={imageDialogOpen} onOpenChange={setImageDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Загрузка скриншота</DialogTitle>
              <DialogDescription>
                Прикрепите PNG или JPEG для анализа ошибки.
              </DialogDescription>
            </DialogHeader>
            <FileDropzone
              accept={{ "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"] }}
              description="Поддерживаются PNG и JPEG."
              fileName={pendingImage?.name}
              onFileSelect={async (file) => {
                const dataUrl = await fileToDataUrl(file);
                setPendingImage({
                  name: file.name,
                  previewUrl: dataUrl,
                  base64: dataUrl,
                });
                setImageDialogOpen(false);
              }}
            />
          </DialogContent>
        </Dialog>
      </>
    );
  }

  if (conversationsQuery.isError) {
    return (
      <ApiStateCard
        title="Support-чат ждёт backend endpoint"
        description="Публичный `/chat` уже подключён к FastAPI, но список и история диалогов для панели поддержки сервер пока не публикует."
        detail={
          conversationsQuery.error instanceof Error
            ? conversationsQuery.error.message
            : undefined
        }
        actionHref="/"
        actionLabel="Открыть дашборд"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-secondary">Чаты</h1>
          <p className="mt-2 text-slate-500">
            Вопрос-ответ, пассивное подключение и эскалации оператору.
          </p>
        </div>
        {detailMode && conversation ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Ellipsis className="h-4 w-4" />
                Управление
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>Архивировать</DropdownMenuItem>
              <DropdownMenuItem>Изменить приоритет</DropdownMenuItem>
              <DropdownMenuItem>Пометить как resolved</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <Card className="h-[calc(100vh-14rem)]">
          <CardHeader>
            <CardTitle>Список диалогов</CardTitle>
          </CardHeader>
          <CardContent className="h-[calc(100%-5rem)] p-0">
            <ScrollArea className="h-full">
              <div className="space-y-2 p-4">
                {conversationsQuery.data?.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => router.push(`/chat/support/${item.id}`)}
                    className={`w-full rounded-xl border p-4 text-left transition-colors ${
                      item.id === selectedId
                        ? "border-secondary bg-secondary text-white"
                        : "border-border bg-white hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium">{item.userName}</p>
                      <Badge className={item.id === selectedId ? "bg-white text-secondary" : ""}>
                        {item.status}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm opacity-80">{item.subject}</p>
                    <p className="mt-2 line-clamp-2 text-sm opacity-70">
                      {item.lastMessage}
                    </p>
                    <p className="mt-3 text-xs opacity-60">
                      {formatDateTime(item.lastMessageAt)}
                    </p>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
        <Card className="h-[calc(100vh-14rem)]">
          <CardHeader className="border-b border-border pb-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>{conversation?.subject ?? "Выберите диалог"}</CardTitle>
                <p className="mt-2 text-sm text-slate-500">
                  {conversation
                    ? `${conversation.userName} · ${conversation.channel}`
                    : "Загрузка истории"}
                </p>
              </div>
              {conversation ? <Badge>{conversation.priority}</Badge> : null}
            </div>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-5.5rem)] flex-col p-0">
            <ScrollArea className="flex-1">
              <div className="space-y-4 p-6">
                {conversationQuery.isLoading ? (
                  <div className="flex h-64 items-center justify-center">
                    <Spinner className="h-6 w-6" />
                  </div>
                ) : null}
                {conversation?.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
              </div>
            </ScrollArea>
            <Separator />
            <div className="space-y-4 p-6">
              {pendingImage ? (
                <div className="rounded-xl border border-border bg-slate-50 p-3">
                  <p className="text-sm font-medium text-secondary">{pendingImage.name}</p>
                  <Image
                    src={pendingImage.previewUrl}
                    alt={pendingImage.name}
                    width={640}
                    height={360}
                    unoptimized
                    className="mt-3 max-h-40 rounded-lg border border-border"
                  />
                </div>
              ) : null}
              <Textarea
                rows={4}
                placeholder="Введите сообщение пользователю или оператору"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setImageDialogOpen(true)}>
                    <ImagePlus className="h-4 w-4" />
                    Прикрепить скриншот
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      toast({
                        title: "Запрос передан оператору",
                        description: "Диалог будет показан в операторской.",
                      })
                    }
                  >
                    <ShieldAlert className="h-4 w-4" />
                    Эскалировать оператору
                  </Button>
                </div>
                <Button onClick={() => sendMutation.mutate()} disabled={sendMutation.isPending}>
                  <Send className="h-4 w-4" />
                  Отправить
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
        {conversation ? (
          <OperatorAssistPanel
            conversation={conversation}
            onSendDraft={() =>
              toast({
                title: "Черновик отправлен",
                description: "Оператор подтвердил ответ пользователю.",
              })
            }
            onEditDraft={() =>
              setDraft((current) => current || conversation.suggestedResponse)
            }
          />
        ) : (
          <Card className="h-[calc(100vh-14rem)]">
            <CardContent className="flex h-full items-center justify-center text-slate-500">
              Выберите диалог
            </CardContent>
          </Card>
        )}
      </div>
      <Dialog open={imageDialogOpen} onOpenChange={setImageDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Загрузка скриншота</DialogTitle>
            <DialogDescription>
              Изображение будет отправлено в анализ вместе с сообщением.
            </DialogDescription>
          </DialogHeader>
          <FileDropzone
            accept={{ "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"] }}
            description="Поддерживаются PNG и JPEG."
            fileName={pendingImage?.name}
            onFileSelect={async (file) => {
              const dataUrl = await fileToDataUrl(file);
              setPendingImage({
                name: file.name,
                previewUrl: dataUrl,
                base64: dataUrl,
              });
              setImageDialogOpen(false);
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
