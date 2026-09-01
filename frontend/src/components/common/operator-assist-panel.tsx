import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Button } from "@/src/components/ui/button";
import { Separator } from "@/src/components/ui/separator";
import type { ConversationDetail } from "@/src/types/domain";

export function OperatorAssistPanel({
  conversation,
  onSendDraft,
  onEditDraft,
}: {
  conversation: ConversationDetail;
  onSendDraft: () => void;
  onEditDraft: () => void;
}) {
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
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {conversation.suggestedResponse}
          </p>
        </div>
        <div className="flex gap-2">
          <Button className="flex-1" onClick={onSendDraft}>
            Отправить
          </Button>
          <Button variant="outline" className="flex-1" onClick={onEditDraft}>
            Редактировать
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
