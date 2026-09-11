"use client";

import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CircleCheck,
  Ellipsis,
  Headset,
  ImagePlus,
  Lock,
  MessageCircle,
  RefreshCw,
  Send,
  type LucideIcon,
} from "lucide-react";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { FileDropzone } from "@/src/components/common/file-dropzone";
import { ConversationThread } from "@/src/components/common/conversation-thread";
import { GuestHistoryList } from "@/src/components/common/guest-history-list";
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
import { Tabs, TabsList, TabsTrigger } from "@/src/components/ui/tabs";
import { Textarea } from "@/src/components/ui/textarea";
import type { ConversationStatus } from "@/src/types/api";
import type {
  ConversationDetail,
  ConversationListItem,
  ConversationMessage,
  UserSession,
} from "@/src/types/domain";
import { useConversation } from "@/src/hooks/use-conversation";
import { useToast } from "@/src/hooks/use-toast";
import { formatDateTime } from "@/src/lib/format";
import { cn } from "@/src/lib/utils";
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

type ConversationStatusFilter = ConversationStatus | "all";

const STATUS_FILTERS: { value: ConversationStatusFilter; label: string }[] = [
  { value: "escalated", label: "Эскалировано" },
  { value: "open", label: "Открыто" },
  { value: "resolved", label: "Закрыто" },
  { value: "all", label: "Все" },
];

const CONVERSATION_STATUS_META: Record<
  ConversationStatus,
  { label: string; icon: LucideIcon; chipClass: string; iconClass: string }
> = {
  open: {
    label: "Открыт",
    icon: MessageCircle,
    chipClass: "border-primary/20 bg-primary/10 text-primary shadow-none",
    iconClass: "bg-primary/10 text-primary",
  },
  escalated: {
    label: "Эскалирован",
    icon: Headset,
    chipClass:
      "border-[#e85646]/25 bg-[#e85646]/10 text-[#c44e3e] shadow-none",
    iconClass: "bg-[#e85646]/10 text-[#c44e3e]",
  },
  resolved: {
    label: "Закрыт",
    icon: CircleCheck,
    chipClass: "border-secondary/15 bg-secondary/8 text-secondary shadow-none",
    iconClass: "bg-secondary/10 text-secondary",
  },
};

function conversationStatusChipClass(status: ConversationStatus): string {
  return CONVERSATION_STATUS_META[status].chipClass;
}

/** Одна карточка очереди: одинаковый каркас, статус — иконка и чип. */
function ConversationListRow({
  item,
  isActive,
  onSelect,
}: {
  item: ConversationListItem;
  isActive: boolean;
  onSelect: () => void;
}) {
  const meta = CONVERSATION_STATUS_META[item.status];
  const Icon = meta.icon;
  const isEscalated = item.status === "escalated";

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={isActive ? "true" : undefined}
      className={cn(
        "conversation-list-row w-full overflow-hidden rounded-[18px] border bg-white p-3.5 text-left transition-colors",
        "border-border hover:border-secondary/25 hover:bg-slate-50/70",
        isActive &&
          "border-secondary/40 bg-secondary/[0.04] shadow-[0_8px_20px_rgba(27,51,85,0.08)]",
        isEscalated && "escalation-corner",
        isEscalated && isActive && "escalation-corner-active",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
            meta.iconClass,
          )}
          aria-hidden="true"
        >
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-secondary">
            {item.userId}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="min-w-0 flex-1 truncate text-xs text-slate-500">
              Создан {formatDateTime(item.createdAt)}
            </p>
            <Badge className={cn("shrink-0 gap-1", meta.chipClass)}>
              <Icon className="h-3 w-3" aria-hidden="true" />
              {meta.label}
            </Badge>
          </div>
        </div>
      </div>
    </button>
  );
}

/**
 * Закрытый тред = открытый circuit: поле ввода не монтируем.
 * Вместо него — маленькая табличка (graceful degradation), не баннер-тревога.
 */
function ClosedComposerPlaque({
  description,
  action,
}: {
  description: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="closed-composer-plaque flex flex-wrap items-center gap-3 rounded-[22px] border border-secondary/15 bg-slate-50/90 px-3.5 py-2.5"
      role="status"
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary/10 text-secondary"
        aria-hidden="true"
      >
        <Lock className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-secondary">Диалог закрыт</p>
        <p className="text-xs leading-5 text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  );
}

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
    history: guestHistory,
    setConversationId: setGuestConversationId,
    resetConversation,
    rememberConversation,
    forgetConversation,
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
  const [statusFilter, setStatusFilter] = useState<ConversationStatusFilter>(
    "escalated",
  );
  const [pendingImage, setPendingImage] = useState<{
    name: string;
    previewUrl: string;
  } | null>(null);

  const isSupportMode = mode === "support";
  const installationId = user?.installationId ?? DEFAULT_INSTALLATION_ID;

  const conversationsQuery = useQuery({
    queryKey: ["conversations", installationId, page, statusFilter],
    queryFn: () =>
      chatService.listConversations(
        installationId,
        page,
        CONVERSATIONS_PAGE_SIZE,
        statusFilter === "all" ? undefined : statusFilter,
      ),
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
        if (
          !selectedId ||
          !text ||
          conversationQuery.data?.status !== "escalated"
        ) {
          return null;
        }
        await chatService.sendOperatorReply(selectedId, installationId, text);
        return { kind: "operator" as const };
      }
      const forceHandoff = Boolean(options?.forceHandoff);
      if (conversationQuery.data?.status === "resolved") {
        return null;
      }
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
        if (selectedId) {
          queryClient.setQueryData(
            ["conversation", installationId, selectedId],
            (current: ConversationDetail | null | undefined) =>
              current ? { ...current, status: "resolved" } : current,
          );
        }
        void queryClient.invalidateQueries({
          queryKey: ["conversation", installationId, selectedId],
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
      setStatusFilter("resolved");
      setPage(1);
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      await queryClient.invalidateQueries({ queryKey: ["conversation"] });
      toast({ title: "Диалог закрыт" });
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

  useEffect(() => {
    if (isSupportMode || !conversation) {
      return;
    }
    rememberConversation({
      id: conversation.id,
      preview: conversation.lastMessage,
      status: conversation.status,
      updatedAt: conversation.lastMessageAt,
    });
  }, [conversation, isSupportMode, rememberConversation]);

  useEffect(() => {
    if (isSupportMode || !guestConversationId) {
      return;
    }
    if (conversationQuery.isSuccess && conversationQuery.data === null) {
      forgetConversation(guestConversationId);
    }
  }, [
    conversationQuery.data,
    conversationQuery.isSuccess,
    forgetConversation,
    guestConversationId,
    isSupportMode,
  ]);

  const beginGuestSession = (): void => {
    guestSessionGeneration.current += 1;
    setGuestSessionEpoch(guestSessionGeneration.current);
    setPendingGuestGeneration(null);
    setGuestMessages([]);
    setDraft("");
    setPendingImage(null);
  };

  const handleNewGuestConversation = (): void => {
    beginGuestSession();
    resetConversation();
  };

  const handleOpenGuestConversation = (conversationId: string): void => {
    if (conversationId === guestConversationId) {
      return;
    }
    beginGuestSession();
    setGuestConversationId(conversationId);
  };

  if (!isSupportMode) {
    return (
      <>
        <Card className="shell-panel reveal-item reveal-delay-4 overflow-hidden rounded-[30px]">
          <CardContent className="grid gap-0 p-0 xl:grid-cols-[minmax(0,1fr)_minmax(260px,320px)]">
            <div className="flex h-[640px] min-h-0 flex-col">
              <div className="flex shrink-0 flex-wrap items-start justify-between gap-4 border-b border-border/60 px-6 py-5">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-primary">
                    Гостевой канал
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-secondary">
                    Гостевой чат поддержки 1С
                  </h2>
                  {guestClosed ? (
                    <Badge className="mt-3 border-secondary/20 bg-white text-secondary">
                      Закрыт
                    </Badge>
                  ) : guestEscalated ? (
                    <Badge className="mt-3 border-warning/30 bg-warning/10 text-warning">
                      Эскалировано оператору
                    </Badge>
                  ) : null}
                </div>
                <Button
                  type="button"
                  variant={guestClosed ? "default" : "outline"}
                  className={cn(
                    "new-dialog-button",
                    guestClosed && "new-dialog-button-cta",
                  )}
                  onClick={handleNewGuestConversation}
                >
                  <RefreshCw className="h-4 w-4" />
                  Новый диалог
                </Button>
              </div>
              <ScrollArea className="min-h-0 flex-1">
                {guestVisibleMessages.length === 0 &&
                !(
                  Boolean(guestConversationId) && conversationQuery.isLoading
                ) ? (
                  <div className="p-6">
                    <div className="rounded-[26px] border border-dashed border-border bg-slate-50/80 p-6">
                      <p className="text-base font-medium text-secondary">
                        Опишите проблему, код ошибки, форму 1С или приложите
                        скриншот.
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-500">
                        Чем точнее контекст обращения, тем релевантнее подбор
                        источников и итоговый ответ.
                      </p>
                    </div>
                  </div>
                ) : (
                  <ConversationThread
                    key={`${guestConversationId ?? "new"}-${guestSessionEpoch}`}
                    conversationId={guestConversationId}
                    messages={guestVisibleMessages}
                    isLoading={
                      Boolean(guestConversationId) &&
                      conversationQuery.isLoading &&
                      guestVisibleMessages.length === 0
                    }
                    hideConfidence
                  />
                )}
                {guestSendPending ? (
                  <div className="px-6 pb-6">
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
                  </div>
                ) : null}
              </ScrollArea>
              <Separator className="shrink-0" />
              <div className="shrink-0 p-6">
                {guestClosed ? (
                  <ClosedComposerPlaque
                    description="Нажмите «Новый диалог», чтобы начать обращение заново."
                    action={
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="shrink-0"
                        onClick={handleNewGuestConversation}
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Новый диалог
                      </Button>
                    }
                  />
                ) : (
                  <div className="space-y-4">
                    {pendingImage ? (
                      <div className="rounded-xl border border-border bg-slate-50 p-3">
                        <p className="text-sm font-medium text-secondary">
                          {pendingImage.name}
                        </p>
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
                      onKeyDown={(event) => {
                        if (event.key !== "Enter" || event.shiftKey) {
                          return;
                        }
                        event.preventDefault();
                        if (!guestSendPending) {
                          sendMutation.mutate();
                        }
                      }}
                    />
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => setImageDialogOpen(true)}
                        >
                          <ImagePlus className="h-4 w-4" />
                          Прикрепить скриншот
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() =>
                            sendMutation.mutate({ forceHandoff: true })
                          }
                          disabled={guestSendPending || guestEscalated}
                        >
                          <Headset className="h-4 w-4" />
                          Позвать оператора
                        </Button>
                      </div>
                      <Button
                        type="button"
                        onClick={() => sendMutation.mutate()}
                        disabled={guestSendPending}
                      >
                        <Send className="h-4 w-4" />
                        Отправить вопрос
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <aside className="flex min-h-0 flex-col border-t border-border/60 bg-slate-50/70 p-5 xl:h-[640px] xl:border-l xl:border-t-0">
              <GuestHistoryList
                className="min-h-0 flex-1"
                items={guestHistory}
                activeId={guestConversationId}
                onSelect={handleOpenGuestConversation}
                onNew={handleNewGuestConversation}
              />
            </aside>
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
            Очередь оператора: эскалации, черновик и ответ гостю.
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
        <Card className="flex h-[calc(100vh-14rem)] flex-col">
          <CardHeader className="shrink-0 gap-3">
            <CardTitle>Список диалогов</CardTitle>
            <Tabs
              value={statusFilter}
              onValueChange={(value) => {
                setStatusFilter(value as ConversationStatusFilter);
                setPage(1);
              }}
            >
              <TabsList
                aria-label="Фильтр диалогов"
                className="status-filter-tray grid h-auto w-full grid-cols-2 gap-[3px] rounded-[16px] bg-secondary/8 p-1"
              >
                {STATUS_FILTERS.map((filter) => (
                  <TabsTrigger
                    key={filter.value}
                    value={filter.value}
                    className="status-filter-item rounded-[12px] px-2 text-[11px] font-semibold text-secondary shadow-none data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-[0_6px_14px_rgba(0,166,80,0.28)]"
                  >
                    {filter.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className="flex min-h-0 flex-1 flex-col p-0">
            <ScrollArea className="flex-1">
              <div className="space-y-2 p-4">
                {conversations?.map((item) => (
                  <ConversationListRow
                    key={item.id}
                    item={item}
                    isActive={item.id === selectedId}
                    onSelect={() => router.push(`/chat/support/${item.id}`)}
                  />
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
        <Card
          className={cn(
            "h-[calc(100vh-14rem)]",
            conversation?.status === "escalated" && "escalation-corner",
            conversation?.status === "resolved" && "resolved-thread",
          )}
        >
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
              {conversation ? (
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Badge className={conversationStatusChipClass(conversation.status)}>
                    {CONVERSATION_STATUS_META[conversation.status].label}
                  </Badge>
                  <Badge>{conversation.priority}</Badge>
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-5.5rem)] flex-col p-0">
            <ScrollArea className="flex-1">
              <ConversationThread
                key={selectedId ?? "empty"}
                conversationId={selectedId}
                messages={conversation?.messages}
                isLoading={Boolean(selectedId) && conversationQuery.isLoading}
              />
            </ScrollArea>
            <Separator />
            <div className="p-6">
              {conversation?.status === "resolved" ? (
                <ClosedComposerPlaque description="Отправка в эту ветку недоступна." />
              ) : (
                <div className="space-y-4">
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
                          draft.trim() || conversation?.suggestedResponse.trim()
                        )
                      }
                    >
                      <Send className="h-4 w-4" />
                      Отправить
                    </Button>
                  </div>
                </div>
              )}
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
