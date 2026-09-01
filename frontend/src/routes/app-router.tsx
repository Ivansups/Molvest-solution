import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/src/components/common/app-shell";
import { AnalyticsPage } from "@/src/components/pages/analytics-page";
import { ChatDetailPage } from "@/src/components/pages/chat-detail-page";
import { ChatPage } from "@/src/components/pages/chat-page";
import { DashboardPage } from "@/src/components/pages/dashboard-page";
import { KnowledgeBasePage } from "@/src/components/pages/knowledge-base-page";
import { KnowledgeDocumentPage } from "@/src/components/pages/knowledge-document-page";
import { LoginPage } from "@/src/components/pages/login-page";
import { OperatorPage } from "@/src/components/pages/operator-page";
import { SettingsPage } from "@/src/components/pages/settings-page";
import { useApp } from "@/src/hooks/use-app-context";

function ProtectedRoutes() {
  const { currentUser } = useApp();

  if (!currentUser) {
    return <Navigate to="/chat" replace />;
  }

  return <AppShell />;
}

function OperatorOnly() {
  const { currentUser } = useApp();
  if (currentUser?.role !== "operator") {
    return <Navigate to="/" replace />;
  }
  return <OperatorPage />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/chat" element={<ChatPage mode="guest" />} />
      <Route element={<ProtectedRoutes />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/chat/support" element={<ChatPage mode="support" />} />
        <Route path="/chat/support/:ticketId" element={<ChatDetailPage />} />
        <Route path="/chat/:ticketId" element={<Navigate to="/chat/support" replace />} />
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="/knowledge-base/:docId" element={<KnowledgeDocumentPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/operator" element={<OperatorOnly />} />
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
