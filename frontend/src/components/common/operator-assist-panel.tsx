import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Button } from "@/src/components/ui/button";
import { Separator } from "@/src/components/ui/separator";
import { Spinner } from "@/src/components/ui/spinner";
import type { ConversationDetail } from "@/src/types/domain";

export function OperatorAssistPanel({
  conversation,
  generatePending = false,
  resolvePending = false,
  sendPending = false,
  canSend = false,
  onGenerateDraft,
  onSendDraft,
  onEditDraft,
  onResolve,
}: {
  conversation: ConversationDetail;
  generatePending?: boolean;
  resolvePending?: boolean;
  sendPending?: boolean;
  canSend?: boolean;
  onGenerateDraft: () => void;
  onSendDraft: () => void;
  onEditDraft: () => void;
  onResolve: () => void;
}) {
  const draft = conversation.suggestedResponse.trim();
  const escalated = conversation.status === "escalated";
  const busy = generatePending || resolvePending || sendPending;
  return (
    <Card className="h-full">
      <CardHeader className="border-b border-border/60 pb-4">
        <CardTitle>Панель оператора</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-[22px] bg-slate-50/80 p-4">
          <p className="text-sm font-medium text-secondary">
            {conversation.userName}
          </p>
          <p className="text-sm text-slate-500">{conversation.userProfile.department}</p>
          <p className="text-sm text-slate-500">{conversation.channel}</p>
        </div>
        <Separator />
        <div className="rounded-[22px] bg-slate-50/80 p-4">
          <p className="text-sm font-medium text-secondary">Рекомендованный ответ</p>
          {generatePending ? (
            <div className="mt-3 flex items-center gap-2 text-sm text-slate-500">
              <Spinner className="h-4 w-4" />
              Агент готовит черновик
            </div>
          ) : null}
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {draft || "Черновик пуст. Нажмите «Сгенерировать ответ», когда будете готовы."}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <Button
            variant="outline"
            onClick={onGenerateDraft}
            disabled={busy || !escalated}
          >
            Сгенерировать ответ
          </Button>
          <div className="flex gap-2">
            <Button
              className="flex-1"
              onClick={onSendDraft}
              disabled={!escalated || (!draft && !canSend) || busy}
            >
              Отправить
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              onClick={onEditDraft}
              disabled={!draft || busy}
            >
              Редактировать
            </Button>
          </div>
          <Button
            variant="outline"
            onClick={onResolve}
            disabled={!escalated || busy}
          >
            Закрыть диалог
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
