export type FileType = "PDF" | "DOCX" | "HTML" | "MD";

export type DocumentStatus = "PENDING" | "INDEXED" | "FAILED";

export type ConversationStatus = "open" | "escalated" | "resolved";

export type MessageRole = "user" | "assistant" | "system" | "operator";

export interface SourceItem {
  document_id: string;
  title: string;
  chunk_text: string;
}

export interface ChatRequest {
  message_id: string;
  workspace_id: string;
  conversation_id: string | null;
  text: string | null;
  image_base64: string | null;
  user_id: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  text: string;
  confidence: number;
  escalated: boolean;
  sources: SourceItem[];
}

export interface ChunkOut {
  id: string;
  content: string;
  chunk_index: number;
}

export interface DocumentOut {
  id: string;
  installation_id: string;
  title: string;
  file_name: string;
  file_type: FileType;
  status: DocumentStatus;
  uploaded_at: string;
  indexed_at: string | null;
  metadata: Record<string, unknown>;
}

export interface DocumentDetailOut extends DocumentOut {
  chunks: ChunkOut[];
}

export interface DocumentListOut {
  items: DocumentOut[];
  page: number;
  page_size: number;
  total: number;
}

