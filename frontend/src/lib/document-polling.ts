import type { DocumentListOut, DocumentStatus } from "@/src/types/api";

export const DOCUMENT_POLL_INTERVAL_MS = 4000;

/** Возвращает интервал списка, пока хотя бы один документ ещё индексируется. */
export function getDocumentsPollingInterval(
  data: Pick<DocumentListOut, "items"> | undefined,
): number | false {
  return data?.items.some((item) => item.status === "PENDING")
    ? DOCUMENT_POLL_INTERVAL_MS
    : false;
}

/** Возвращает интервал карточки только для документа в статусе PENDING. */
export function getDocumentPollingInterval(
  status: DocumentStatus | undefined,
): number | false {
  return status === "PENDING" ? DOCUMENT_POLL_INTERVAL_MS : false;
}
