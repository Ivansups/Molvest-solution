import type { DocumentListOut, DocumentStatus } from "@/src/types/api";

export const DOCUMENT_POLL_INTERVAL_MS = 4000;

const watchingIds = new Set<string>();

/** Начинает следить за документом после загрузки или реиндекса. */
export function watchDocument(id: string): void {
  watchingIds.add(id);
}

export function unwatchDocument(id: string): void {
  watchingIds.delete(id);
}

/** Сброс для тестов. */
export function clearWatchedDocuments(): void {
  watchingIds.clear();
}

function releaseFinished(id: string, status: DocumentStatus | undefined): void {
  if (status !== undefined && status !== "PENDING") {
    watchingIds.delete(id);
  }
}

/** Интервал списка: только документы, которые мы сами поставили в очередь. */
export function getDocumentsPollingInterval(
  data: Pick<DocumentListOut, "items"> | undefined,
): number | false {
  if (watchingIds.size === 0) {
    return false;
  }

  for (const item of data?.items ?? []) {
    releaseFinished(item.id, item.status);
  }

  const shouldPoll = data?.items.some(
    (item) => watchingIds.has(item.id) && item.status === "PENDING",
  );
  return shouldPoll ? DOCUMENT_POLL_INTERVAL_MS : false;
}

/** Интервал карточки: только если этот документ мы сами поставили в очередь. */
export function getDocumentPollingInterval(
  docId: string | undefined,
  status: DocumentStatus | undefined,
): number | false {
  if (!docId || !watchingIds.has(docId)) {
    return false;
  }
  releaseFinished(docId, status);
  return watchingIds.has(docId) && status === "PENDING"
    ? DOCUMENT_POLL_INTERVAL_MS
    : false;
}
