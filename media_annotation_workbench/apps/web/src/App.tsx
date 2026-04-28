import { useEffect, useState } from "react";

import { LoginForm } from "./components/LoginForm";
import { Sidebar } from "./components/Sidebar";
import { fetchCurrentUser, fetchDashboardSummary, fetchSnapshots, login } from "./lib/api";
import type { DashboardSummary, Snapshot, UserInfo } from "./lib/types";
import { AssetBrowserPage } from "./pages/AssetBrowserPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocsPage } from "./pages/DocsPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";

const STORAGE_TOKEN_KEY = "media_workbench_token";
const STORAGE_USER_KEY = "media_workbench_user";

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STORAGE_TOKEN_KEY));
  const [user, setUser] = useState<UserInfo | null>(() => {
    const raw = localStorage.getItem(STORAGE_USER_KEY);
    return raw ? (JSON.parse(raw) as UserInfo) : null;
  });
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  async function loadWorkbenchData(activeToken: string) {
    const [resolvedUser, resolvedSummary, resolvedSnapshots] = await Promise.all([
      fetchCurrentUser(activeToken),
      fetchDashboardSummary(activeToken),
      fetchSnapshots(activeToken),
    ]);
    setUser(resolvedUser);
    setSummary(resolvedSummary);
    setSnapshots(resolvedSnapshots);
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(resolvedUser));
  }

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadWorkbenchData(token).catch((caught) => {
      setBootError(caught instanceof Error ? caught.message : "初始化失败");
      localStorage.removeItem(STORAGE_TOKEN_KEY);
      localStorage.removeItem(STORAGE_USER_KEY);
      setToken(null);
      setUser(null);
    });
  }, [token]);

  async function handleLogin(username: string, password: string) {
    const response = await login(username, password);
    localStorage.setItem(STORAGE_TOKEN_KEY, response.access_token);
    localStorage.setItem(STORAGE_USER_KEY, JSON.stringify(response.user));
    setToken(response.access_token);
    setUser(response.user);
    await loadWorkbenchData(response.access_token);
    setBootError(null);
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_TOKEN_KEY);
    localStorage.removeItem(STORAGE_USER_KEY);
    setToken(null);
    setUser(null);
    setSummary(null);
    setSnapshots([]);
    setCurrentPage("dashboard");
  }

  if (!token || !user) {
    return <LoginForm onSubmit={handleLogin} />;
  }

  return (
    <div className="app-frame">
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} onLogout={handleLogout} user={user} />
      <main className="content-shell">
        {bootError ? <div className="error-banner">{bootError}</div> : null}
        {currentPage === "dashboard" ? (
          <DashboardPage token={token} user={user} summary={summary} snapshots={snapshots} onRefresh={() => loadWorkbenchData(token)} />
        ) : null}
        {currentPage === "assets" ? <AssetBrowserPage token={token} summary={summary} /> : null}
        {currentPage === "reviews" ? (
          <ReviewQueuePage token={token} user={user} activeSnapshotId={summary?.active_snapshot?.snapshot_id} />
        ) : null}
        {currentPage === "docs" ? <DocsPage token={token} summary={summary} /> : null}
      </main>
    </div>
  );
}
