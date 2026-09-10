import { beforeEach, describe, expect, it } from "vitest";
import {
  DOCUMENT_POLL_INTERVAL_MS,
  clearWatchedDocuments,
  getDocumentPollingInterval,
  getDocumentsPollingInterval,
  watchDocument,
} from "@/src/lib/document-polling";
import type { DocumentListOut } from "@/src/types/api";

const documentList = (
  rows: Array<{ id: string; status: DocumentListOut["items"][number]["status"] }>,
) => ({
  items: rows.map((row) => ({
    id: row.id,
    installation_id: "installation",
    title: row.id,
    file_name: `${row.id}.pdf`,
    file_type: "PDF" as const,
    status: row.status,
    uploaded_at: "2026-09-10T00:00:00Z",
    indexed_at: null,
    metadata: {},
  })),
});

describe("document polling", () => {
  beforeEach(() => {
    clearWatchedDocuments();
  });

  it("does not poll the list just because a document is pending", () => {
    expect(
      getDocumentsPollingInterval(documentList([{ id: "a", status: "PENDING" }])),
    ).toBe(false);
  });

  it("polls the list only for documents watched after upload or reindex", () => {
    watchDocument("b");
    expect(
      getDocumentsPollingInterval(
        documentList([
          { id: "a", status: "PENDING" },
          { id: "b", status: "PENDING" },
        ]),
      ),
    ).toBe(DOCUMENT_POLL_INTERVAL_MS);
  });

  it("stops list polling when the watched document is final", () => {
    watchDocument("b");
    expect(
      getDocumentsPollingInterval(
        documentList([
          { id: "a", status: "PENDING" },
          { id: "b", status: "INDEXED" },
        ]),
      ),
    ).toBe(false);
  });

  it("does not poll the list when the watched document is not on this page", () => {
    watchDocument("missing");
    expect(
      getDocumentsPollingInterval(documentList([{ id: "a", status: "PENDING" }])),
    ).toBe(false);
  });

  it("does not poll a pending card that we did not start indexing", () => {
    expect(getDocumentPollingInterval("a", "PENDING")).toBe(false);
  });

  it("polls the card only while the watched document is pending", () => {
    watchDocument("a");
    expect(getDocumentPollingInterval("a", "PENDING")).toBe(
      DOCUMENT_POLL_INTERVAL_MS,
    );
  });

  it.each(["INDEXED", "FAILED"] as const)(
    "stops card polling for watched %s",
    (status) => {
      watchDocument("a");
      expect(getDocumentPollingInterval("a", status)).toBe(false);
    },
  );
});
