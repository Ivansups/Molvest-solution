import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { FileDropzone } from "@/src/components/common/file-dropzone";
import { Button } from "@/src/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/src/components/ui/dialog";
import { Input } from "@/src/components/ui/input";
import { Label } from "@/src/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/src/components/ui/select";
import { Textarea } from "@/src/components/ui/textarea";
import type { FileType } from "@/src/types/api";

const schema = z.object({
  title: z.string().min(3, "Введите название документа"),
  category: z.string().min(2, "Укажите категорию"),
  description: z.string().min(5, "Добавьте короткое описание"),
  fileType: z.enum(["PDF", "DOCX", "HTML", "MD"]),
});

type FormValues = z.infer<typeof schema>;

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: FormValues & { file: File | null }) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      category: "",
      description: "",
      fileType: "PDF",
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    await onSubmit({ ...values, file });
    setFile(null);
    form.reset();
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Добавить документ</DialogTitle>
          <DialogDescription>
            Новый документ будет отправлен в очередь индексации базы знаний.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="title">Название</Label>
            <Input id="title" {...form.register("title")} />
            <p className="text-sm text-destructive">{form.formState.errors.title?.message}</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="category">Категория</Label>
              <Input id="category" {...form.register("category")} />
              <p className="text-sm text-destructive">
                {form.formState.errors.category?.message}
              </p>
            </div>
            <div className="grid gap-2">
              <Label>Тип файла</Label>
              <Controller
                control={form.control}
                name="fileType"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(value) => field.onChange(value as FileType)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите тип" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="PDF">PDF</SelectItem>
                      <SelectItem value="DOCX">DOCX</SelectItem>
                      <SelectItem value="HTML">HTML</SelectItem>
                      <SelectItem value="MD">Markdown</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">Описание</Label>
            <Textarea id="description" rows={4} {...form.register("description")} />
            <p className="text-sm text-destructive">
              {form.formState.errors.description?.message}
            </p>
          </div>
          <FileDropzone
            accept={{
              "application/pdf": [".pdf"],
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                [".docx"],
              "text/markdown": [".md"],
              "text/html": [".html"],
            }}
            description="Поддерживаются PDF, DOCX, HTML и Markdown."
            fileName={file?.name}
            onFileSelect={setFile}
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Отменить
            </Button>
            <Button type="submit">Добавить</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
