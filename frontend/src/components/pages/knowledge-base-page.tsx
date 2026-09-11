"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Files, Pencil, Plus, RefreshCcw, Search, SearchX, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { ApiStateCard } from "@/src/components/common/api-state-card";
import { DataTablePagination } from "@/src/components/common/data-table-pagination";
import { DocumentStatusBadge } from "@/src/components/common/document-status-badge";
import { DocumentUploadDialog } from "@/src/components/common/document-upload-dialog";
import { Button } from "@/src/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/src/components/ui/card";
import { Input } from "@/src/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/src/components/ui/select";
import { Spinner } from "@/src/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/src/components/ui/table";
import { useToast } from "@/src/hooks/use-toast";
import {
  getDocumentsPollingInterval,
  unwatchDocument,
  watchDocument,
} from "@/src/lib/document-polling";
import { formatDateTime } from "@/src/lib/format";
import { documentService } from "@/src/services/document-service";
import type { FileType } from "@/src/types/api";

export function KnowledgeBasePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);

  const documentsQuery = useQuery({
    queryKey: ["documents", page, search, type],
    queryFn: () =>
      documentService.listDocuments({
        page,
        pageSize: 10,
        search,
        type,
      }),
    refetchInterval: (query) => getDocumentsPollingInterval(query.state.data),
  });

  const createMutation = useMutation({
    mutationFn: async (values: {
      title: string;
      category: string;
      description: string;
      fileType: FileType;
      file: File | null;
    }) =>
      documentService.createDocument({
        title: values.title,
        fileType: values.fileType,
        file: values.file,
        metadata: {
          category: values.category,
          description: values.description,
          originalFileName: values.file?.name ?? values.title,
        },
      }),
    onSuccess: async (document) => {
      watchDocument(document.id);
      setPage(1);
      setDialogOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Документ добавлен",
        description: "Файл поставлен в очередь индексации.",
      });
    },
    onError: (error) =>
      toast({
        title: "Не удалось добавить документ",
        description: error instanceof Error ? error.message : "Проверьте backend.",
        variant: "destructive",
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => documentService.deleteDocument(docId),
    onSuccess: async (_result, docId) => {
      unwatchDocument(docId);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast({
        title: "Документ удалён",
        description: "Связанные данные базы знаний очищены.",
      });
    },
    onError: (error) =>
      toast({
        title: "Не удалось удалить документ",
        description: error instanceof Error ? error.message : "Проверьте backend.",
        variant: "destructive",
      }),
  });

  const reindexMutation = useMutation({
    mutationFn: (docId: string) => documentService.reindexDocument(docId),
    onSuccess: async (_result, docId) => {
      watchDocument(docId);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      await queryClient.invalidateQueries({ queryKey: ["document", docId] });
      toast({
        title: "Реиндексация запущена",
        description: "Документ переведён в актуальное состояние.",
      });
    },
    onError: (error) =>
      toast({
        title: "Не удалось запустить реиндексацию",
        description: error instanceof Error ? error.message : "Проверьте backend.",
        variant: "destructive",
      }),
  });

  if (documentsQuery.isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (!documentsQuery.data) {
    return (
      <ApiStateCard
        title="База знаний недоступна"
        description="Раздел больше не использует mock-данные и ожидает живой backend."
        detail={documentsQuery.error instanceof Error ? documentsQuery.error.message : undefined}
        actionHref="/chat"
        actionLabel="Открыть публичный чат"
      />
    );
  }

  const items = documentsQuery.data.items;
  const hasActiveFilters = search.trim() !== "" || type !== "all";
  const showEmptyState = items.length === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-secondary">База знаний</h1>
          <p className="mt-2 text-slate-500">
            Управление документами, чанками и актуальностью контента.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="h-4 w-4" />
          Добавить документ
        </Button>
      </div>
      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle>Реестр документов</CardTitle>
          <div className="flex flex-col gap-3 md:flex-row">
            <div className="relative min-w-72">
              <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Поиск по названию"
                value={search}
                onChange={(event) => {
                  setPage(1);
                  setSearch(event.target.value);
                }}
                className="pl-9"
              />
            </div>
            <Select
              value={type}
              onValueChange={(value) => {
                setPage(1);
                setType(value);
              }}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder="Фильтр по типу" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все типы</SelectItem>
                <SelectItem value="PDF">PDF</SelectItem>
                <SelectItem value="DOCX">DOCX</SelectItem>
                <SelectItem value="HTML">HTML</SelectItem>
                <SelectItem value="MD">Markdown</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className={showEmptyState ? "px-6 pb-8 pt-0" : "p-0"}>
          {showEmptyState ? (
            <DocumentsEmptyState
              filtered={hasActiveFilters}
              onAdd={() => setDialogOpen(true)}
              onReset={() => {
                setSearch("");
                setType("all");
                setPage(1);
              }}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead>Тип</TableHead>
                    <TableHead>Дата обновления</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead className="text-right">Действия</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <button
                          type="button"
                          className="text-left font-medium text-secondary hover:underline"
                          onClick={() => router.push(`/knowledge-base/${item.id}`)}
                        >
                          {item.title}
                        </button>
                      </TableCell>
                      <TableCell>{item.file_type}</TableCell>
                      <TableCell>{formatDateTime(item.uploaded_at)}</TableCell>
                      <TableCell>
                        <DocumentStatusBadge status={item.status} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => router.push(`/knowledge-base/${item.id}`)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => reindexMutation.mutate(item.id)}
                          >
                            <RefreshCcw className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteMutation.mutate(item.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <DataTablePagination
                page={page}
                pageSize={10}
                total={documentsQuery.data.total}
                onPageChange={setPage}
              />
            </>
          )}
        </CardContent>
      </Card>
      <DocumentUploadDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={async (values) => {
          await createMutation.mutateAsync(values);
        }}
      />
    </div>
  );
}

function DocumentsEmptyState({
  filtered,
  onAdd,
  onReset,
}: {
  filtered: boolean;
  onAdd: () => void;
  onReset: () => void;
}) {
  const Icon = filtered ? SearchX : Files;
  const title = filtered ? "Ничего не найдено" : "Документов пока нет";
  const hint = filtered
    ? "Измените название или тип файла — в реестре нет подходящих документов."
    : "Загрузите инструкцию, регламент или справку — агент будет отвечать по этим материалам.";

  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary/10 text-secondary">
        <Icon className="h-6 w-6" />
      </div>
      <h2 className="mt-4 text-lg font-semibold text-secondary">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{hint}</p>
      {filtered ? (
        <Button variant="outline" className="mt-5" onClick={onReset}>
          Сбросить фильтры
        </Button>
      ) : (
        <Button className="mt-5" onClick={onAdd}>
          <Plus className="h-4 w-4" />
          Добавить документ
        </Button>
      )}
    </div>
  );
}
