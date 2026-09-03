import type {
  ChatRequest,
  ChatResponse,
  DocumentDetailOut,
  DocumentStatus,
  FileType,
} from "@/src/types/api";
import { DEFAULT_INSTALLATION_ID } from "@/src/lib/installation";
import type {
  ActiveTicket,
  AnalyticsData,
  AuditLogItem,
  ConversationDetail,
  ConversationMessage,
  DashboardData,
  SystemSettings,
} from "@/src/types/domain";

const installationId = DEFAULT_INSTALLATION_ID;

const now = "2026-09-01T10:00:00.000Z";

function createDocument(
  id: string,
  title: string,
  fileType: FileType,
  status: DocumentStatus,
  uploadedAt: string,
  metadata: Record<string, unknown>,
): DocumentDetailOut {
  return {
    id,
    installation_id: installationId,
    title,
    file_name: `${title}.${fileType.toLowerCase()}`,
    file_type: fileType,
    status,
    uploaded_at: uploadedAt,
    indexed_at: status === "INDEXED" ? now : null,
    metadata,
    chunks: [
      {
        id: `${id}-chunk-1`,
        chunk_index: 0,
        content:
          "Проверка прав пользователя, статуса обмена и регламентных заданий.",
      },
      {
        id: `${id}-chunk-2`,
        chunk_index: 1,
        content:
          "Пошаговые инструкции для бухгалтерии и операторов поддержки 1С.",
      },
    ],
  };
}

let documents: DocumentDetailOut[] = [
  createDocument(
    "3f6546a8-2471-48b0-bfc5-f8647387960f",
    "Регламент обработки ошибок 1С",
    "PDF",
    "INDEXED",
    "2026-08-30T08:40:00.000Z",
    { category: "Регламенты", owner: "Линия 1", source: "Внутренняя БЗ" },
  ),
  createDocument(
    "7fb9b20b-d6d8-4b7a-90b4-e64bb53ac2a7",
    "Инструкция по обмену с Bitrix24",
    "DOCX",
    "INDEXED",
    "2026-08-29T11:20:00.000Z",
    { category: "Интеграции", owner: "Линия 2", source: "Bitrix24" },
  ),
  createDocument(
    "94f49350-3b8c-4d6a-a7b0-7ae4d3217fa8",
    "Типовые ошибки закрытия смены",
    "MD",
    "PENDING",
    "2026-08-31T15:00:00.000Z",
    { category: "Касса", owner: "Линия 1", source: "Экспертная статья" },
  ),
];

function createMessage(
  id: string,
  role: ConversationMessage["role"],
  content: string,
  createdAt: string,
  options?: Partial<ConversationMessage>,
): ConversationMessage {
  return {
    id,
    role,
    content,
    createdAt,
    ...options,
  };
}

const conversations: ConversationDetail[] = [
  {
    id: "60dc157f-f66a-4b8e-bdb6-e8e317ebce20",
    subject: "Ошибка при проведении расходной накладной",
    userId: "u-001",
    userName: "Ирина Соколова",
    channel: "Bitrix24",
    status: "escalated",
    lastMessage:
      "После обновления формы поле «Договор» снова не заполняется автоматически.",
    lastMessageAt: "2026-09-01T09:47:00.000Z",
    priority: "high",
    unread: 2,
    suggestedResponse:
      "Проверьте обязательность поля «Договор» в расширении формы и права роли.",
    userProfile: {
      company: "АО «Молвест»",
      department: "Бухгалтерия",
      position: "Старший бухгалтер",
      lastSeenAt: "2026-09-01T09:48:00.000Z",
    },
    messages: [
      createMessage(
        "m-001",
        "user",
        "Не проводится расходная накладная, пишет что договор не заполнен.",
        "2026-09-01T09:37:00.000Z",
      ),
      createMessage(
        "m-002",
        "assistant",
        "Проверьте, выбран ли контрагент и заполнен ли договор в шапке документа.",
        "2026-09-01T09:38:00.000Z",
        {
          confidence: 0.84,
          sources: [
            {
              document_id: documents[0].id,
              title: documents[0].title,
              chunk_text: documents[0].chunks[0].content,
            },
          ],
        },
      ),
      createMessage(
        "m-003",
        "user",
        "Прикладываю скриншот. После обновления это происходит у нескольких пользователей.",
        "2026-09-01T09:45:00.000Z",
        {
          imageUrl:
            "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'><rect width='100%' height='100%' fill='%23edf3f8'/><rect x='40' y='40' width='560' height='280' rx='16' fill='white' stroke='%231a3b6b' stroke-width='2'/><text x='70' y='110' font-size='22' fill='%231a3b6b'>Ошибка 1С: Не заполнено поле \"Договор\"</text><text x='70' y='160' font-size='18' fill='%232c3e50'>Форма: Расходная накладная</text><text x='70' y='200' font-size='18' fill='%232c3e50'>Пользователь: Бухгалтер филиала</text></svg>",
          screenshotAnalysis: {
            recognizedText:
              "Ошибка 1С: Не заполнено поле «Договор». Форма: Расходная накладная.",
            suggestions: [
              "Проверить обязательность реквизита после обновления конфигурации.",
              "Убедиться, что у роли пользователя есть право на чтение договора.",
            ],
          },
        },
      ),
      createMessage(
        "m-004",
        "system",
        "Диалог передан оператору из-за уверенности ниже порога 80%.",
        "2026-09-01T09:47:00.000Z",
        { escalated: true, confidence: 0.61 },
      ),
    ],
  },
  {
    id: "e6d12cf0-dc93-4375-bc89-fc57e3de2a76",
    subject: "Не запускается обмен с Bitrix24",
    userId: "u-002",
    userName: "Павел Гордеев",
    channel: "Bitrix24",
    status: "open",
    lastMessage: "Подскажите, где посмотреть лог последней синхронизации?",
    lastMessageAt: "2026-09-01T08:52:00.000Z",
    priority: "medium",
    unread: 0,
    suggestedResponse:
      "Лог синхронизации находится в разделе Интеграции → История обмена.",
    userProfile: {
      company: "АО «Молвест»",
      department: "ИТ-служба",
      position: "Системный администратор",
      lastSeenAt: "2026-09-01T08:53:00.000Z",
    },
    messages: [
      createMessage(
        "m-005",
        "user",
        "Подскажите, где посмотреть лог последней синхронизации?",
        "2026-09-01T08:49:00.000Z",
      ),
      createMessage(
        "m-006",
        "assistant",
        "Откройте раздел «Интеграции», затем вкладку «История обмена».",
        "2026-09-01T08:50:00.000Z",
        { confidence: 0.92 },
      ),
    ],
  },
  {
    id: "f9304167-8b0c-42ef-90e9-cf7f2219e0f2",
    subject: "Письмо из Redmine не создало тикет",
    userId: "u-003",
    userName: "Марина Жданова",
    channel: "Redmine",
    status: "resolved",
    lastMessage: "Спасибо, правило маршрутизации помогло.",
    lastMessageAt: "2026-08-31T16:15:00.000Z",
    priority: "low",
    unread: 0,
    suggestedResponse:
      "Проверено правило маршрутизации почты и домен отправителя.",
    userProfile: {
      company: "АО «Молвест»",
      department: "HR",
      position: "Специалист отдела кадров",
      lastSeenAt: "2026-08-31T16:20:00.000Z",
    },
    messages: [
      createMessage(
        "m-007",
        "user",
        "Отправила письмо в поддержку, но тикет не создался.",
        "2026-08-31T15:58:00.000Z",
      ),
      createMessage(
        "m-008",
        "operator",
        "Проблема была в правиле маршрутизации, уже исправили.",
        "2026-08-31T16:12:00.000Z",
      ),
    ],
  },
];

const auditLogs: AuditLogItem[] = [
  {
    id: "log-1",
    type: "system",
    title: "Порог уверенности обновлён",
    description: "Оператор изменил порог эскалации с 0.75 до 0.8.",
    actor: "Анна Лебедева",
    createdAt: "2026-09-01T09:10:00.000Z",
    severity: "warning",
  },
  {
    id: "log-2",
    type: "chat",
    title: "Диалог эскалирован",
    description: "Запрос по расходной накладной передан оператору.",
    actor: "Molvest AI",
    createdAt: "2026-09-01T09:47:00.000Z",
    severity: "info",
  },
  {
    id: "log-3",
    type: "kb",
    title: "Документ поставлен в очередь индексации",
    description: "«Типовые ошибки закрытия смены» отправлен на reindex.",
    actor: "Екатерина Романова",
    createdAt: "2026-08-31T15:05:00.000Z",
    severity: "info",
  },
  {
    id: "log-4",
    type: "operator",
    title: "Черновик ответа подтверждён",
    description: "Оператор отправил пользователю скорректированный ответ.",
    actor: "Смена операторов",
    createdAt: "2026-08-31T16:12:00.000Z",
    severity: "info",
  },
];

let settings: SystemSettings = {
  general: {
    workspaceName: "Molvest AI Support",
    supportEmail: "support@molvest.ru",
    autoReplyEnabled: true,
    responseSlaSeconds: 5,
  },
  escalation: {
    confidenceThreshold: 0.8,
    autoConnectEnabled: true,
    defaultQueue: "Линия 1",
  },
  integrations: {
    bitrixWebhook: "https://bitrix.molvest.ru/rest/ai-agent",
    redmineMailbox: "helpdesk@molvest.ru",
    syncEmailCases: true,
  },
  models: {
    generationModel: "GigaChat-2-Pro",
    embeddingsModel: "Embeddings-1536",
    visionEnabled: true,
  },
};

function paginate<T>(items: T[], page: number, pageSize: number) {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export function getInstallationId() {
  return installationId;
}

export function getDashboardData(): DashboardData {
  const escalated = conversations.filter((item) => item.status === "escalated").length;
  const autoReplyRate = 0.68;
  return {
    metrics: [
      { label: "Всего обращений", value: "1 284", hint: "+8% за неделю" },
      { label: "Автоответы", value: "68%", hint: "цель 70%" },
      { label: "Среднее время ответа", value: "4.2 сек", hint: "ниже SLA 5 сек" },
      { label: "Эскалации", value: String(escalated), hint: "требуют внимания" },
    ],
    trends: [
      { date: "2026-08-26", tickets: 110, autoReplies: 76, escalations: 34 },
      { date: "2026-08-27", tickets: 134, autoReplies: 90, escalations: 44 },
      { date: "2026-08-28", tickets: 121, autoReplies: 82, escalations: 39 },
      { date: "2026-08-29", tickets: 150, autoReplies: 104, escalations: 46 },
      { date: "2026-08-30", tickets: 138, autoReplies: 99, escalations: 39 },
      { date: "2026-08-31", tickets: 126, autoReplies: 88, escalations: 38 },
      { date: "2026-09-01", tickets: 118, autoReplies: Math.round(118 * autoReplyRate), escalations: 38 },
    ],
    recentChats: conversations,
    logs: auditLogs,
  };
}

export function getAnalyticsData(): AnalyticsData {
  return {
    trends: getDashboardData().trends,
    distribution: [
      { name: "Автоответы", value: 68 },
      { name: "Эскалации", value: 32 },
    ],
    logs: auditLogs,
  };
}

export function listConversations() {
  return conversations.map((item) => ({
    id: item.id,
    subject: item.subject,
    userId: item.userId,
    userName: item.userName,
    channel: item.channel,
    status: item.status,
    lastMessage: item.lastMessage,
    lastMessageAt: item.lastMessageAt,
    priority: item.priority,
    unread: item.unread,
    suggestedResponse: item.suggestedResponse,
  }));
}

export function getConversation(id: string) {
  return conversations.find((item) => item.id === id) ?? null;
}

export function upsertConversationMessage(
  request: ChatRequest,
  imageUrl?: string,
): ChatResponse {
  const target = request.conversation_id
    ? conversations.find((item) => item.id === request.conversation_id)
    : createGuestConversation(request.user_id);

  if (!target) {
    throw new Error("Conversation not found");
  }

  const userMessage = createMessage(
    request.message_id,
    "user",
    request.text ?? "Пользователь отправил изображение",
    new Date().toISOString(),
    imageUrl
      ? {
          imageUrl,
          screenshotAnalysis: {
            recognizedText:
              "Обнаружен текст ошибки 1С и обязательное поле, не заполненное в документе.",
            suggestions: [
              "Проверить настройки формы документа после обновления.",
              "Сопоставить ошибку с базой знаний по ключевым словам.",
            ],
          },
        }
      : undefined,
  );

  target.messages = [...target.messages, userMessage];

  const escalated = (request.text ?? "").toLowerCase().includes("снова");
  const responseText = escalated
    ? "Уверенность ниже порога. Черновик передан оператору для проверки."
    : "Рекомендуем проверить обязательность поля и права роли пользователя.";

  const assistantMessage = createMessage(
    `assistant-${request.message_id}`,
    escalated ? "system" : "assistant",
    responseText,
    new Date().toISOString(),
    {
      confidence: escalated ? 0.61 : 0.88,
      escalated,
      sources: [
        {
          document_id: documents[0].id,
          title: documents[0].title,
          chunk_text: documents[0].chunks[0].content,
        },
      ],
    },
  );

  target.messages = [...target.messages, assistantMessage];
  target.lastMessage = assistantMessage.content;
  target.lastMessageAt = assistantMessage.createdAt;
  target.status = escalated ? "escalated" : target.status;
  target.unread = escalated ? target.unread + 1 : target.unread;

  return {
    conversation_id: target.id,
    message_id: assistantMessage.id,
    text: assistantMessage.content,
    confidence: assistantMessage.confidence ?? 0.88,
    escalated,
    sources: assistantMessage.sources ?? [],
  };
}

function createGuestConversation(userId: string): ConversationDetail {
  const conversation: ConversationDetail = {
    id: crypto.randomUUID(),
    subject: "Гостевой вопрос по 1С",
    userId,
    userName: "Гость",
    channel: "Bitrix24",
    status: "open",
    lastMessage: "",
    lastMessageAt: new Date().toISOString(),
    priority: "medium",
    unread: 0,
    suggestedResponse:
      "Проверьте формулировку вопроса и при необходимости приложите скриншот.",
    userProfile: {
      company: "АО «Молвест»",
      department: "Пользователь",
      position: "Гостевой доступ",
      lastSeenAt: new Date().toISOString(),
    },
    messages: [],
  };

  conversations.unshift(conversation);
  return conversation;
}

export function listDocuments(page = 1, pageSize = 10, search = "", type = "all") {
  const searchLower = search.toLowerCase();
  const filtered = documents.filter((item) => {
    const bySearch =
      !searchLower ||
      item.title.toLowerCase().includes(searchLower) ||
      item.file_name.toLowerCase().includes(searchLower);
    const byType = type === "all" || item.file_type === type;
    return bySearch && byType;
  });

  return {
    items: paginate(filtered, page, pageSize).map((item) => ({
      id: item.id,
      installation_id: item.installation_id,
      title: item.title,
      file_name: item.file_name,
      file_type: item.file_type,
      status: item.status,
      uploaded_at: item.uploaded_at,
      indexed_at: item.indexed_at,
      metadata: item.metadata,
    })),
    total: filtered.length,
  };
}

export function getDocument(id: string) {
  return documents.find((item) => item.id === id) ?? null;
}

export function createDocumentEntry(
  title: string,
  fileType: FileType,
  metadata: Record<string, unknown>,
) {
  const id = crypto.randomUUID();
  const entry = createDocument(id, title, fileType, "PENDING", new Date().toISOString(), metadata);
  documents = [entry, ...documents];
  return entry;
}

export function updateDocumentEntry(
  id: string,
  payload: {
    title: string;
    category: string;
    description: string;
  },
) {
  documents = documents.map((item) =>
    item.id === id
      ? {
          ...item,
          title: payload.title,
          file_name: `${payload.title}.${item.file_type.toLowerCase()}`,
          metadata: {
            ...item.metadata,
            category: payload.category,
            description: payload.description,
          },
        }
      : item,
  );

  return getDocument(id);
}

export function deleteDocumentEntry(id: string) {
  documents = documents.filter((item) => item.id !== id);
}

export function reindexDocumentEntry(id: string) {
  documents = documents.map((item) =>
    item.id === id
      ? {
          ...item,
          status: "INDEXED",
          indexed_at: new Date().toISOString(),
        }
      : item,
  );
  return getDocument(id);
}

export function getActiveTickets(): ActiveTicket[] {
  return conversations
    .filter((item) => item.status === "escalated")
    .map((item) => ({
      id: item.id,
      subject: item.subject,
      userName: item.userName,
      escalatedAt: item.lastMessageAt,
      channel: item.channel,
      priority: item.priority,
      draft: item.suggestedResponse,
    }));
}

export function getSettings() {
  return settings;
}

export function saveSettings(nextSettings: SystemSettings) {
  settings = nextSettings;
  return settings;
}

export function getAuditLogs() {
  return auditLogs;
}
