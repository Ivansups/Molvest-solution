import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();

vi.mock("@/src/api/admin-client", () => ({
  adminApiClient: { get, post, patch, delete: vi.fn() },
}));

const { documentService } = await import("@/src/services/document-service");

const documentOut = {
  id: "d1",
  installation_id: "i1",
  title: "Инструкция",
  file_name: "guide.pdf",
  file_type: "PDF" as const,
  status: "PENDING" as const,
  uploaded_at: "2026-09-13T00:00:00Z",
  indexed_at: null,
  metadata: {},
};

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
});

describe("documentService replace file", () => {
  it("posts the file to /documents/:id/file", async () => {
    const file = new File(["%PDF-1.4 v2"], "guide.pdf", { type: "application/pdf" });
    post.mockResolvedValue({ data: documentOut });
    get.mockResolvedValue({ data: { ...documentOut, chunks: [] } });

    const result = await documentService.replaceDocumentFile("d1", file);

    expect(post).toHaveBeenCalledOnce();
    expect(post.mock.calls[0]?.[0]).toBe("/documents/d1/file");
    const body = post.mock.calls[0]?.[1] as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBe(file);
    expect(result?.id).toBe("d1");
    expect(get).toHaveBeenCalledWith("/documents/d1");
  });

  it("does not patch metadata when replacing a file", async () => {
    const file = new File(["# v2"], "guide.md", { type: "text/markdown" });
    post.mockResolvedValue({ data: { ...documentOut, file_name: "guide.md" } });
    get.mockResolvedValue({
      data: { ...documentOut, file_name: "guide.md", chunks: [] },
    });

    await documentService.replaceDocumentFile("d1", file);

    expect(patch).not.toHaveBeenCalled();
  });
});

describe("documentService metadata patch", () => {
  it("patches title and metadata without uploading a file", async () => {
    patch.mockResolvedValue({ data: documentOut });
    get.mockResolvedValue({ data: { ...documentOut, chunks: [] } });

    await documentService.updateDocumentMetadata({
      docId: "d1",
      title: "Новое имя",
      category: "1С",
      description: "Как провести документ",
    });

    expect(patch).toHaveBeenCalledWith("/documents/d1", {
      title: "Новое имя",
      metadata: {
        category: "1С",
        description: "Как провести документ",
      },
    });
    expect(post).not.toHaveBeenCalled();
  });
});
