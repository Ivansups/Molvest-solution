"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ellipsis,
  Headset,
  ImagePlus,
  RefreshCw,
  Send,
} from "lucide-react";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { FileDropzone } from "@/src/components/common/file-dropzone";
import { MessageBubble } from "@/src/components/common/message-bubble";
import { OperatorAssistPanel } from "@/src/components/common/operator-assist-panel";
import { ResolveConfirmationDialog } from "@/src/components/common/resolve-confirmation-dialog";
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
import type { ConversationDetail, ConversationMessage, UserSession } from "@/src/types/domain";
import { useConversation } from "@/src/hooks/use-conversation";
import { useToast } from "@/src/hooks/use-toast";
import { formatDateTime } from "@/src/lib/format";
import {
  GUEST_HANDOFF_TEXT,
  isActiveGuestSend,
  isStaleGuestGeneration,
} from "@/src/lib/guest-session";
import { dataUrlToBase64, fileToCompressedDataUrl } from "@/src/lib/image";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import { chatService } from "@/src/services/chat-service";
import { ApiServiceError } from "@/src/services/service-helpers";

const CONVERSATIONS_PAGE_SIZE = 50;

async function attachScreenshot(file: File): Promise<{
  name: string;
  previewUrl: string;
}> {
  // data-URL, а не createObjectURL: превью переезжает в историю сообщений,
  // где revokeObjectURL уже негде вызвать.
  return { name: file.name, previewUrl: await fileToCompressedDataUrl(file) };
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
  const {
    conversationId: guestConversationId,
    setConversationId: setGuestConversationId,
    resetConversation,
  } = useConversation();
  const guestSessionGeneration = useRef(0);
  const [guestSessionEpoch, setGuestSessionEpoch] = useState(0);
  const [pendingGuestGeneration, setPendingGuestGeneration] = useState<
    number | null
  >(null);
  const [guestMessages, setGuestMessages] = useState<ConversationMessage[]>([]);
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pendingImage, setPendingImage] = useState<{
    name: string;
    previewUrl: string;
  } | null>(null);

  const isSupportMode = mode === "support";
  const installationId = user?.installationId ?? DEFAULT_INSTALLATION_ID;

  const conversationsQuery = useQuery({
    queryKey: ["conversations", installationId, page],
    queryFn: () =>
      chatService.listConversations(installationId, page, CONVERSATIONS_PAGE_SIZE, "escalated"),
    enabled: isSupportMode,
    refetchInterval: 5_000,
  });

  const conversations = conversationsQuery.data?.items;
  const total = conversationsQuery.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / CONVERSATIONS_PAGE_SIZE));

  const selectedId = isSupportMode
    ? ticketId ?? conversations?.[0]?.id ?? null
    : guestConversationId;

  useEffect(() => {
    if (isSupportMode && !ticketId && conversations?.[0]?.id) {
      router.replace(`/chat/support/${conversations[0].id}`);
    }
  }, [conversations, isSupportMode, router, ticketId]);

  const conversationQuery = useQuery({
    queryKey: ["conversation", installationId, selectedId],
    queryFn: () => chatService.getConversation(selectedId ?? "", installationId),
    enabled: Boolean(selectedId) && (isSupportMode || Boolean(guestConversationId)),
    refetchInterval: (query) => {
      if (isSupportMode) {
        return 5_000;
      }
      return query.state.data?.status === "escalated" ? 5_000 : false;
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (options?: { forceHandoff?: boolean }) => {
      if (isSupportMode) {
        const text =
          draft.trim() || conversationQuery.data?.suggestedResponse?.trim() || "";
        if (!selectedId || !text) {
          return null;
        }
        await chatService.sendOperatorReply(selectedId, installationId, text);
        return { kind: "operator" as const };
      }
      const forceHandoff = Boolean(options?.forceHandoff);
      if (!forceHandoff && !draft.trim() && !pendingImage) {
        return null;
      }

      const alreadyEscalated = Boolean(
        conversationQuery.data?.status === "escalated" ||
          conversationQuery.data?.messages.some((message) => message.escalated) ||
          guestMessages.some((message) => message.escalated),
      );
      const userContent = forceHandoff
        ? GUEST_HANDOFF_TEXT
        : draft.trim() || "Пользователь отправил изображение";
      const imageUrl = forceHandoff ? undefined : pendingImage?.previewUrl;
      const guestUserId = `guest-${guestConversationId ?? "session"}`;
      const data = await chatService.sendMessage({
        message_id: crypto.randomUUID(),
        workspace_id: installationId,
        conversation_id: selectedId,
        text: forceHandoff ? GUEST_HANDOFF_TEXT : draft.trim() || null,
        image_base64:
          forceHandoff || !pendingImage
            ? null
            : dataUrlToBase64(pendingImage.previewUrl),
        user_id: user?.id ?? guestUserId,
        ...(forceHandoff ? { force_handoff: true } : {}),
      });
      return {
        kind: "guest" as const,
        data,
        userContent,
        imageUrl,
        alreadyEscalated,
        forceHandoff,
      };
    },
    onMutate: (): { generation: number } => {
      const generation = guestSessionGeneration.current;
      if (!isSupportMode) {
        setPendingGuestGeneration(generation);
      }
      return { generation };
    },
    onSuccess: async (result, _variables, context) => {
      if (!result) {
        return;
      }

      if (result.kind === "guest") {
        if (
          context === undefined ||
          isStaleGuestGeneration(
            context.generation,
            guestSessionGeneration.current,
          )
        ) {
          return;
        }
        setDraft("");
        setPendingImage(null);
        const createdAt = new Date().toISOString();
        const conversationId = result.data.conversation_id;
        const userMessage: ConversationMessage = {
          id: crypto.randomUUID(),
          role: "user",
          content: result.userContent,
          createdAt,
          imageUrl: result.imageUrl,
        };
        const replyMessage: ConversationMessage = {
          id: result.data.message_id,
          role: result.data.escalated ? "system" : "assistant",
          content: result.data.text,
          createdAt,
          confidence: result.data.confidence,
          escalated: result.data.escalated,
          sources: result.data.sources,
        };
        const showReply = result.forceHandoff || !result.alreadyEscalated;
        setGuestConversationId(conversationId);
        setGuestMessages((current) => {
          const next = [...current, userMessage];
          if (showReply) {
            next.push(replyMessage);
          }
          return next;
        });
        queryClient.setQueryData(
          ["conversation", installationId, conversationId],
          (current: ConversationDetail | null | undefined) => {
            if (!current) {
              return current;
            }
            return {
              ...current,
              messages: showReply
                ? [...current.messages, userMessage, replyMessage]
                : [...current.messages, userMessage],
            };
          },
        );
        toast({
          title:
            result.data.escalated && !result.alreadyEscalated
              ? "Диалог эскалирован"
              : "Сообщение отправлено",
          description: showReply ? result.data.text : undefined,
        });
      } else {
        setDraft("");
        toast({ title: "Ответ отправлен" });
      }
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({
        queryKey: ["conversation", installationId, selectedId],
      });
    },
    onError: (error, _variables, context) => {
      if (
        !isSupportMode &&
        (context === undefined ||
          isStaleGuestGeneration(
            context.generation,
            guestSessionGeneration.current,
          ))
      ) {
        return;
      }
      if (error instanceof ApiServiceError && error.status === 409) {
        toast({
          title: "Диалог закрыт",
          description: "Оператор уже закрыл обращение.",
        });
        return;
      }
      toast({
        title: "Backend не ответил",
        description: error instanceof Error ? error.message : "Повторите запрос позже.",
        variant: "destructive",
      });
    },
    onSettled: (_data, _error, _variables, context) => {
      if (
        !isSupportMode &&
        context !== undefined &&
        context.generation === guestSessionGeneration.current
      ) {
        setPendingGuestGeneration(null);
      }
    },
  });

  const generateMutation = useMutation({
    mutationFn: () => {
      if (!selectedId) {
        return Promise.resolve(null);
      }
      return chatService.generateSuggestion(selectedId, installationId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["conversation"] });
    },
    onError: (error) =>
      toast({
        title: "Не удалось сгенерировать ответ",
        description: error instanceof Error ? error.message : undefined,
        variant: "destructive",
      }),
  });

  const resolveMutation = useMutation({
    mutationFn: (comment?: string) => {
      if (!selectedId) {
        return Promise.resolve();
      }
      return chatService.resolveConversation(
        selectedId,
        installationId,
        comment,
      );
    },
    onSuccess: async () => {
      setResolveDialogOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["conversation"] });
      toast({ title: "Диалог закрыт" });
      if (isSupportMode) {
        router.replace("/chat/support");
      }
    },
    onError: (error) =>
      toast({
        title: "Не удалось закрыть диалог",
        description: error instanceof Error ? error.message : undefined,
        variant: "destructive",
      }),
  });

  const conversation = conversationQuery.data;
  const guestVisibleMessages = conversationQuery.data?.messages ?? guestMessages;
  const guestEscalated = conversationQuery.data?.status === "escalated";
  const guestClosed = conversationQuery.data?.status === "resolved";
  const guestSendPending = isActiveGuestSend(
    pendingGuestGeneration,
    guestSessionEpoch,
  );

  const handleNewGuestConversation = (): void => {
    guestSessionGeneration.current += 1;
    setGuestSessionEpoch(guestSessionGeneration.current);
    setPendingGuestGeneration(null);
    resetConversation();
    setGuestMessages([]);
    setDraft("");
    setPendingImage(null);
  };

  if (!isSupportMode) {
    return (
      <>
        <Card className="shell-panel reveal-item reveal-delay-4 overflow-hidden rounded-[30px]">
          <CardContent className="grid gap-0 p-0 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-h-[640px] flex-col">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/60 px-6 py-5">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-primary">
                    Гостевой канал
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-secondary">
                    Гостевой чат поддержки 1С
                  </h2>
                  {guestEscalated ? (
                    <Badge className="mt-3 border-warning/30 bg-warning/10 text-warning">
                      Эскалировано оператору
                    </Badge>
                  ) : null}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="new-dialog-button"
                  onClick={handleNewGuestConversation}
                >
                  <RefreshCw className="h-4 w-4" />
                  Новый диалог
                </Button>
              </div>
              <ScrollArea className="flex-1">
                <div className="space-y-4 p-6">
                  {guestVisibleMessages.length === 0 ? (
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
                  {guestVisibleMessages.map((message, index) => (
                    <MessageBubble
                      key={message.id}
                      message={message}
                      animate={index === guestVisibleMessages.length - 1}
                    />
                  ))}
                  {guestSendPending ? (
                    <div className="flex items-center gap-3 rounded-2xl border border-primary/15 bg-primary/5 p-4 text-sm text-secondary">
                      <Spinner className="h-5 w-5 shrink-0" />
                      <span>
                        {pendingImage && !sendMutation.variables?.forceHandoff
                          ? "анализ изображения…"
                          : "агент формирует ответ…"}
                      </span>
                      <span className="typing-dots" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                      </span>
                    </div>
                  ) : null}
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
                  placeholder={
                    guestClosed
                      ? "Диалог закрыт оператором"
                      : "Опишите ошибку, код 1С или приложите скриншот"
                  }
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" || event.shiftKey) {
                      return;
                    }
                    event.preventDefault();
                    if (!guestSendPending && !guestClosed) {
                      sendMutation.mutate();
                    }
                  }}
                  disabled={guestClosed}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setImageDialogOpen(true)}
                      disabled={guestClosed}
                    >
                      <ImagePlus className="h-4 w-4" />
                      Прикрепить скриншот
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => sendMutation.mutate({ forceHandoff: true })}
                      disabled={guestSendPending || guestClosed}
                    >
                      <Headset className="h-4 w-4" />
                      Позвать оператора
                    </Button>
                  </div>
                  <Button
                    type="button"
                    onClick={() => sendMutation.mutate()}
                    disabled={guestSendPending || guestClosed}
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
                setPendingImage(await attachScreenshot(file));
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
        title="Не удалось загрузить список диалогов"
        description="Проверьте, что backend запущен и доступен `/api/conversations`."
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
              <DropdownMenuItem
                onClick={() => setResolveDialogOpen(true)}
                disabled={resolveMutation.isPending || conversation.status !== "escalated"}
              >
                Пометить как resolved
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <Card className="h-[calc(100vh-14rem)]">
          <CardHeader>
            <CardTitle>Список диалогов</CardTitle>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-5rem)] flex-col p-0">
            <ScrollArea className="flex-1">
              <div className="space-y-2 p-4">
                {conversations?.map((item) => (
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
                      <p className="truncate font-medium">{item.userId}</p>
                      <Badge className={item.id === selectedId ? "bg-white text-secondary" : ""}>
                        {item.status}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs opacity-60">
                      Создан {formatDateTime(item.createdAt)}
                    </p>
                  </button>
                ))}
              </div>
            </ScrollArea>
            {total > CONVERSATIONS_PAGE_SIZE ? (
              <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-3">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                >
                  Назад
                </Button>
                <span className="text-xs text-slate-500">
                  {page} / {pageCount} · всего {total}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= pageCount}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Вперёд
                </Button>
              </div>
            ) : null}
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
                {conversation?.messages.map((message, index) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    animate={index === conversation.messages.length - 1}
                  />
                ))}
              </div>
            </ScrollArea>
            <Separator />
            <div className="space-y-4 p-6">
              <Textarea
                rows={4}
                placeholder="Введите сообщение пользователю"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" || event.shiftKey) {
                    return;
                  }
                  event.preventDefault();
                  const canSend =
                    !sendMutation.isPending &&
                    conversation?.status === "escalated" &&
                    Boolean(
                      draft.trim() || conversation?.suggestedResponse.trim(),
                    );
                  if (canSend) {
                    sendMutation.mutate();
                  }
                }}
                disabled={conversation?.status !== "escalated"}
              />
              <div className="flex justify-end">
                <Button
                  onClick={() => sendMutation.mutate()}
                  disabled={
                    sendMutation.isPending ||
                    conversation?.status !== "escalated" ||
                    !(
                      draft.trim() ||
                      conversation?.suggestedResponse.trim()
                    )
                  }
                >
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
            generatePending={generateMutation.isPending}
            resolvePending={resolveMutation.isPending}
            canSend={Boolean(draft.trim() || conversation.suggestedResponse.trim())}
            sendPending={sendMutation.isPending}
            onGenerateDraft={() => generateMutation.mutate()}
            onSendDraft={() => sendMutation.mutate()}
            onEditDraft={() =>
              setDraft((current) => current || conversation.suggestedResponse)
            }
            onResolve={() => setResolveDialogOpen(true)}
          />
        ) : (
          <Card className="h-[calc(100vh-14rem)]">
            <CardContent className="flex h-full items-center justify-center text-slate-500">
              Выберите диалог
            </CardContent>
          </Card>
        )}
      </div>
      <ResolveConfirmationDialog
        open={resolveDialogOpen}
        pending={resolveMutation.isPending}
        onOpenChange={setResolveDialogOpen}
        onConfirm={(comment) => resolveMutation.mutate(comment)}
      />
    </div>
  );
}
