"use client";

import { useState } from "react";
import { Button } from "@/src/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/src/components/ui/dialog";
import { Label } from "@/src/components/ui/label";
import { Textarea } from "@/src/components/ui/textarea";

export function ResolveConfirmationDialog({
  open,
  pending = false,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  pending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (comment: string | undefined) => void;
}) {
  const [comment, setComment] = useState("");

  const closeDialog = (): void => {
    if (pending) {
      return;
    }
    setComment("");
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) {
          onOpenChange(true);
          return;
        }
        closeDialog();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Обращение решено?</DialogTitle>
          <DialogDescription>
            Да закроет диалог. Нет оставит статус «эскалировано» — запрос не
            отправится.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="resolve-comment">Комментарий (необязательно)</Label>
          <Textarea
            id="resolve-comment"
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            disabled={pending}
            placeholder="Коротко, что сделали"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={closeDialog}
          >
            Нет
          </Button>
          <Button
            type="button"
            disabled={pending}
            onClick={() => {
              const nextComment = comment.trim() || undefined;
              setComment("");
              onConfirm(nextComment);
            }}
          >
            Да
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
