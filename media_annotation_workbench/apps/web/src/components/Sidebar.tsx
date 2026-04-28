import type { UserInfo } from "../lib/types";

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  user: UserInfo;
  onLogout: () => void;
}

const navItems = [
  { id: "dashboard", label: "Dashboard" },
  { id: "assets", label: "Asset Browser" },
  { id: "reviews", label: "Review Queue" },
  { id: "docs", label: "Schema & Docs" },
];

export function Sidebar({ currentPage, onNavigate, user, onLogout }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <p className="eyebrow">Media Ops</p>
        <h1>媒介知识与标注工作台</h1>
        <p className="muted-text">知识数据库 + 审核标注台</p>
      </div>

      <nav className="nav-list">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? "nav-item-active" : ""}`}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="user-card">
        <div>
          <strong>{user.display_name}</strong>
          <p className="muted-text">
            {user.username} · {user.role_label}
          </p>
        </div>
        <button className="ghost-button small" onClick={onLogout} type="button">
          退出
        </button>
      </div>
    </aside>
  );
}
