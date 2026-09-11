"use client";

import Image from "next/image";
import { useState } from "react";
import { Bot, FileText, UserCircle2, Wrench } from "lucide-react";
import { Avatar, AvatarFallback } from "@/src/components/ui/avatar";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { cn } from "@/src/lib/utils";
import type { ConversationMessage } from "@/src/types/domain";

const roleMeta = {
  user: { label: "Пользователь", icon: UserCircle2, tone: "bg-white/90" },
  assistant: { label: "AI-агент", icon: Bot, tone: "bg-primary/6" },
  operator: { label: "Оператор", icon: Wrench, tone: "bg-secondary/6" },
  system: { label: "Система", icon: Bot, tone: "bg-amber-50/90" },
} as const;

export function MessageBubble({
  message,
  animate = false,
  hideConfidence = false,
}: {
  message: ConversationMessage;
  animate?: boolean;
  hideConfidence?: boolean;
}) {
  const meta = roleMeta[message.role];
  const Icon = meta.icon;

  return (
    <div
      className={cn(
        "soft-shadow flex gap-3 rounded-[24px] border border-white/70 p-4",
        animate && "reveal-item",
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
          {message.confidence !== undefined && !hideConfidence ? (
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
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-500">Источники</p>
            {message.sources.map((source, index) => (
              <SourceCitation key={`${source.document_id}-${index}`} source={source} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

const SOURCE_EXCERPT_LENGTH = 200;

function excerptChunkText(chunkText: string): string {
  if (chunkText.length <= SOURCE_EXCERPT_LENGTH) {
    return chunkText;
  }
  return `${chunkText.slice(0, SOURCE_EXCERPT_LENGTH).trimEnd()}…`;
}

function SourceCitation({
  source,
}: {
  source: NonNullable<ConversationMessage["sources"]>[number];
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const excerpt = excerptChunkText(source.chunk_text);

  return (
    <div className="rounded-xl border border-primary/15 bg-white/80 p-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-auto w-full justify-start whitespace-normal px-2 py-1.5 text-left text-primary"
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((current) => !current)}
      >
        <FileText className="h-4 w-4 shrink-0" />
        <span>{source.title}</span>
      </Button>
      <p className="px-2 pb-1 pt-2 text-sm leading-6 text-slate-600">
        {isExpanded ? source.chunk_text : excerpt}
      </p>
    </div>
  );
}
