import type {
  ConversationStatus,
  DocumentDetailOut,
  DocumentOut,
  MessageRole,
  SourceItem,
} from "@/src/types/api";

export type AppRole = "admin" | "operator";

export interface UserSession {
  id: string;
  name: string;
  email: string;
  role: AppRole;
  installationId: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  description: string;
  createdAt: string;
}

export interface ScreenshotAnalysis {
  recognizedText: string;
  suggestions: string[];
}

export interface ConversationMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  confidence?: number;
  escalated?: boolean;
  imageUrl?: string;
  sources?: SourceItem[];
  screenshotAnalysis?: ScreenshotAnalysis;
}

export interface ConversationPreview {
  id: string;
  subject: string;
  userId: string;
  userName: string;
  channel: "Bitrix24" | "Redmine";
  status: ConversationStatus;
  lastMessage: string;
  lastMessageAt: string;
  priority: "low" | "medium" | "high";
  unread: number;
  suggestedResponse: string;
}

export interface UserProfile {
  company: string;
  department: string;
  position: string;
  lastSeenAt: string;
}

export interface ConversationDetail extends ConversationPreview {
  userProfile: UserProfile;
  messages: ConversationMessage[];
}

export interface DashboardMetric {
  label: string;
  value: string;
  hint: string;
}

export interface TrendPoint {
  date: string;
  tickets: number;
  autoReplies: number;
  escalations: number;
}

export interface DistributionPoint {
  name: string;
  value: number;
}

export interface AuditLogItem {
  id: string;
  type: "chat" | "kb" | "operator" | "system";
  title: string;
  description: string;
  actor: string;
  createdAt: string;
  severity: "info" | "warning" | "error";
}

export interface DashboardData {
  metrics: DashboardMetric[];
  trends: TrendPoint[];
  recentChats: ConversationPreview[];
  logs: AuditLogItem[];
}

export interface AnalyticsData {
  trends: TrendPoint[];
  distribution: DistributionPoint[];
  logs: AuditLogItem[];
}

export interface KnowledgeBaseData {
  items: DocumentOut[];
  total: number;
}

export interface ActiveTicket {
  id: string;
  subject: string;
  userName: string;
  escalatedAt: string;
  channel: "Bitrix24" | "Redmine";
  priority: "low" | "medium" | "high";
  draft: string;
}

export interface SystemSettings {
  general: {
    workspaceName: string;
    supportEmail: string;
    autoReplyEnabled: boolean;
    responseSlaSeconds: number;
  };
  escalation: {
    confidenceThreshold: number;
    autoConnectEnabled: boolean;
    defaultQueue: string;
  };
  integrations: {
    bitrixWebhook: string;
    redmineMailbox: string;
    syncEmailCases: boolean;
  };
  models: {
    generationModel: string;
    embeddingsModel: string;
    visionEnabled: boolean;
  };
}

export interface DocumentEditorState {
  document: DocumentDetailOut;
  markdownPreview: string;
}

