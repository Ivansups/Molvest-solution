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

export interface ConversationOut {
  id: string;
  installation_id: string;
  user_id: string;
  status: ConversationStatus;
  created_at: string;
  suggested_response: string | null;
}

export interface EscalationOut {
  id: string;
  message_id: string;
  reason: string;
  escalated_to: string;
  resolved_at: string | null;
}

export interface MessageOut {
  id: string;
  role: MessageRole;
  content: string;
  confidence: number | null;
  escalated: boolean;
  sources: SourceItem[];
  created_at: string;
}

export interface ConversationDetailOut {
  id: string;
  installation_id: string;
  user_id: string;
  status: ConversationStatus;
  created_at: string;
  suggested_response: string | null;
  messages: MessageOut[];
  escalations: EscalationOut[];
}

export interface ConversationListOut {
  items: ConversationOut[];
  page: number;
  page_size: number;
  total: number;
}

export interface ConversationMetrics {
  auto_answer_percent: number;
  avg_response_time_seconds: number;
  escalation_count: number;
}

export interface AgentSettings {
  confidence_threshold: number;
  operator_assist_mode: "draft" | "auto";
}

