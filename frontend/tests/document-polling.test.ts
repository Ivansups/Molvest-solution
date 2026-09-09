import { describe, expect, it } from "vitest";
import {
  DOCUMENT_POLL_INTERVAL_MS,
  getDocumentPollingInterval,
  getDocumentsPollingInterval,
} from "@/src/lib/document-polling";
import type { DocumentListOut } from "@/src/types/api";

const documentList = (statuses: DocumentListOut["items"][number]["status"][]) => ({
  items: statuses.map((status, index) => ({
    id: String(index),
    installation_id: "installation",
    title: `Документ ${index}`,
    file_name: `document-${index}.pdf`,
    file_type: "PDF" as const,
    status,
    uploaded_at: "2026-09-09T00:00:00Z",
    indexed_at: null,
    metadata: {},
  })),
});

describe("document polling", () => {
  it("polls the list while any document is pending", () => {
    expect(getDocumentsPollingInterval(documentList(["INDEXED", "PENDING"]))).toBe(
      DOCUMENT_POLL_INTERVAL_MS,
    );
  });

  it("stops list polling when all documents are final", () => {
    expect(getDocumentsPollingInterval(documentList(["INDEXED", "FAILED"]))).toBe(false);
  });

  it("stops list polling for an empty or not-yet-loaded result", () => {
    expect(getDocumentsPollingInterval(documentList([]))).toBe(false);
    expect(getDocumentsPollingInterval(undefined)).toBe(false);
  });

  it("polls the card only while its document is pending", () => {
    expect(getDocumentPollingInterval("PENDING")).toBe(DOCUMENT_POLL_INTERVAL_MS);
  });

  it.each(["INDEXED", "FAILED"] as const)(
    "stops card polling for %s",
    (status) => {
      expect(getDocumentPollingInterval(status)).toBe(false);
    },
  );
});
