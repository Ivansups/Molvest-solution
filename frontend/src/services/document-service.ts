import { apiClient } from "@/src/api/client";
import {
  getStoredInstallationId,
  toServiceError,
  unsupportedEndpoint,
} from "@/src/services/service-helpers";
import type { DocumentDetailOut, DocumentListOut, DocumentOut, FileType } from "@/src/types/api";

export const documentService = {
  async listDocuments(params: {
    page: number;
    pageSize: number;
    search: string;
    type: string;
  }): Promise<DocumentListOut> {
    try {
      const response = await apiClient.get<DocumentListOut>("/api/documents", {
        params: {
          installation_id: getStoredInstallationId(),
          page: params.page,
          page_size: params.pageSize,
          file_type: params.type === "all" ? undefined : params.type,
        },
      });
      const items = response.data.items.filter((item) =>
        params.search
          ? item.title.toLowerCase().includes(params.search.toLowerCase())
          : true,
      );
      return {
        ...response.data,
        items,
        total: params.search ? items.length : response.data.total,
      };
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить список документов.",
        "/api/documents",
      );
    }
  },

  async getDocument(docId: string): Promise<DocumentDetailOut | null> {
    try {
      const response = await apiClient.get<DocumentDetailOut>(`/api/documents/${docId}`);
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить карточку документа.",
        `/api/documents/${docId}`,
      );
    }
  },

  async createDocument(payload: {
    title: string;
    fileType: FileType;
    metadata: Record<string, unknown>;
    file: File | null;
  }): Promise<DocumentOut> {
    if (!payload.file) {
      throw new Error("Выберите файл документа перед загрузкой.");
    }

    try {
      const formData = new FormData();
      formData.append("file", payload.file);
      formData.append("title", payload.title);
      formData.append("installation_id", getStoredInstallationId());
      formData.append("metadata", JSON.stringify(payload.metadata));
      const response = await apiClient.post<DocumentOut>("/api/documents", formData);
      return response.data;
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось загрузить документ в backend.",
        "/api/documents",
      );
    }
  },

  async updateDocumentMetadata(payload: {
    docId: string;
    title: string;
    category: string;
    description: string;
  }): Promise<DocumentDetailOut | null> {
    unsupportedEndpoint(
      `/api/documents/${payload.docId}`,
      "Бэкенд пока не поддерживает обновление метаданных документа через PATCH.",
    );
  },

  async deleteDocument(docId: string): Promise<void> {
    try {
      await apiClient.delete(`/api/documents/${docId}`);
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось удалить документ.",
        `/api/documents/${docId}`,
      );
    }
  },

  async reindexDocument(docId: string): Promise<DocumentDetailOut | null> {
    try {
      await apiClient.post<DocumentOut>(`/api/documents/${docId}/reindex`);
      return await this.getDocument(docId);
    } catch (error) {
      throw toServiceError(
        error,
        "Не удалось запустить реиндексацию документа.",
        `/api/documents/${docId}/reindex`,
      );
    }
  },
};
