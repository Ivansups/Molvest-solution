import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { FileDropzone } from "@/src/components/common/file-dropzone";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
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
import { Spinner } from "@/src/components/ui/spinner";
import { Textarea } from "@/src/components/ui/textarea";
import { useToast } from "@/src/hooks/use-toast";
import { documentService } from "@/src/services/document-service";

const schema = z.object({
  title: z.string().min(3),
  category: z.string().min(2),
  description: z.string().min(5),
});

type FormValues = z.infer<typeof schema>;

export function KnowledgeDocumentPage() {
  const navigate = useNavigate();
  const { docId } = useParams();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [versionFileName, setVersionFileName] = useState<string | null>(null);

  const documentQuery = useQuery({
    queryKey: ["document", docId],
    queryFn: () => documentService.getDocument(docId ?? ""),
    enabled: Boolean(docId),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: "",
      category: "",
      description: "",
    },
  });

  useEffect(() => {
    const document = documentQuery.data;
    if (!document) {
      return;
    }

    form.reset({
      title: document.title,
      category: String(document.metadata.category ?? "Без категории"),
      description: String(document.metadata.description ?? "Без описания"),
    });
  }, [documentQuery.data, form]);

  const updateMutation = useMutation({
    mutationFn: (values: FormValues) =>
      documentService.updateDocumentMetadata({
        docId: docId ?? "",
        title: values.title,
        category: values.category,
        description: values.description,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["document", docId] });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Документ сохранён",
        description: "Метаданные обновлены.",
      });
    },
    onError: (error) =>
      toast({
        title: "Сохранение недоступно",
        description: error instanceof Error ? error.message : "Проверьте backend.",
        variant: "destructive",
      }),
  });

  const handleSave = form.handleSubmit(async (values) => {
    await updateMutation.mutateAsync(values);
  });

  if (documentQuery.isLoading) {
    return (
      <div className="flex h-80 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (!documentQuery.data) {
    return (
      <ApiStateCard
        title="Карточка документа недоступна"
        description="Документ больше не подгружается из mock-слоя и ожидает ответ backend."
        detail={documentQuery.error instanceof Error ? documentQuery.error.message : undefined}
        actionHref="/knowledge-base"
        actionLabel="Вернуться к списку"
      />
    );
  }

  const document = documentQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-secondary">{document.title}</h1>
          <p className="mt-2 text-slate-500">
            Просмотр чанков и редактирование карточки документа.
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate("/knowledge-base")}>
          Назад к списку
        </Button>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Предпросмотр</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-border bg-slate-50 p-4">
              <p className="text-sm font-medium text-secondary">Описание</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {String(document.metadata.description ?? "Описание отсутствует")}
              </p>
            </div>
            <div className="space-y-3">
              {document.chunks.map((chunk) => (
                <div key={chunk.id} className="rounded-xl border border-border p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-400">
                    Chunk {chunk.chunk_index + 1}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{chunk.content}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Метаданные</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSave}>
              <div className="grid gap-2">
                <Label htmlFor="title">Название</Label>
                <Input id="title" {...form.register("title")} />
              </div>
              <div className="grid gap-2">
                <Label>Категория</Label>
                <Controller
                  control={form.control}
                  name="category"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите категорию" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Регламенты">Регламенты</SelectItem>
                        <SelectItem value="Интеграции">Интеграции</SelectItem>
                        <SelectItem value="Касса">Касса</SelectItem>
                        <SelectItem value="1С">1С</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="description">Описание</Label>
                <Textarea id="description" rows={5} {...form.register("description")} />
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={() => setVersionDialogOpen(true)}
              >
                Загрузить новую версию
              </Button>
              {versionFileName ? (
                <p className="text-sm text-slate-500">Выбрана версия: {versionFileName}</p>
              ) : null}
              <div className="rounded-xl border border-warning/25 bg-warning/10 p-3 text-sm leading-6 text-foreground">
                Обновление метаданных через API ещё не опубликовано на backend, поэтому
                эта форма пока работает как подготовленный UI без серверного сохранения.
              </div>
              <div className="flex gap-2">
                <Button type="submit" className="flex-1">
                  Сохранить
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1"
                  onClick={() => form.reset()}
                >
                  Отменить
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
      <Dialog open={versionDialogOpen} onOpenChange={setVersionDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Новая версия документа</DialogTitle>
            <DialogDescription>
              Файл будет использован для следующей переиндексации.
            </DialogDescription>
          </DialogHeader>
          <FileDropzone
            accept={{
              "application/pdf": [".pdf"],
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                [".docx"],
            }}
            description="Выберите новый исходный файл документа."
            fileName={versionFileName ?? undefined}
            onFileSelect={(file) => {
              setVersionFileName(file.name);
              setVersionDialogOpen(false);
              toast({
                title: "Новая версия принята",
                description: "После сохранения можно запустить reindex.",
              });
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
