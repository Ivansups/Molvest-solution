import Image from "next/image";
import { Bot, UserCircle2, Wrench } from "lucide-react";
import { Avatar, AvatarFallback } from "@/src/components/ui/avatar";
import { Badge } from "@/src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { cn } from "@/src/lib/utils";
import type { ConversationMessage } from "@/src/types/domain";

const roleMeta = {
  user: { label: "Пользователь", icon: UserCircle2, tone: "bg-white/90" },
  assistant: { label: "AI-агент", icon: Bot, tone: "bg-primary/6" },
  operator: { label: "Оператор", icon: Wrench, tone: "bg-secondary/6" },
  system: { label: "Система", icon: Bot, tone: "bg-amber-50/90" },
} as const;

export function MessageBubble({ message }: { message: ConversationMessage }) {
  const meta = roleMeta[message.role];
  const Icon = meta.icon;

  return (
    <div
      className={cn(
        "soft-shadow flex gap-3 rounded-[24px] border border-white/70 p-4",
        meta.tone,
      )}
    >
      <Avatar className="h-11 w-11">
        <AvatarFallback>
          <Icon className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-secondary">{meta.label}</p>
          {message.confidence !== undefined ? (
            <Badge>Уверенность {Math.round(message.confidence * 100)}%</Badge>
          ) : null}
          {message.escalated ? (
            <Badge className="border-warning/30 bg-warning/10 text-warning">
              Эскалация
            </Badge>
          ) : null}
        </div>
        <p className="text-sm leading-6 text-foreground">{message.content}</p>
        {message.imageUrl ? (
          <Image
            src={message.imageUrl}
            alt="Скриншот пользователя"
            width={640}
            height={360}
            unoptimized
            className="max-h-64 rounded-xl border border-border object-cover"
          />
        ) : null}
        {message.screenshotAnalysis ? (
          <Card className="border-primary/20 bg-white">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Анализ скриншота</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-sm font-medium text-secondary">Распознанный текст</p>
                <p className="mt-1 text-sm text-slate-500">
                  {message.screenshotAnalysis.recognizedText}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-secondary">
                  Предложения по исправлению
                </p>
                <ul className="mt-1 space-y-1 text-sm text-slate-500">
                  {message.screenshotAnalysis.suggestions.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        ) : null}
        {message.sources?.length ? (
          <div className="flex flex-wrap gap-2">
            {message.sources.map((source, index) => (
              <Badge
                key={`${source.document_id}-${index}`}
                className="bg-white"
              >
                {source.title}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
