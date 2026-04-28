import { useEffect, useMemo, useState } from "react";

import { activateSnapshot, exportReviewedEpisodes, importSnapshot } from "../lib/api";
import type { DashboardSummary, Snapshot, UserInfo } from "../lib/types";

interface DashboardPageProps {
  token: string;
  user: UserInfo;
  summary: DashboardSummary | null;
  snapshots: Snapshot[];
  onRefresh: () => Promise<void>;
}

export function DashboardPage({ token, user, summary, snapshots, onRefresh }: DashboardPageProps) {
  const [sourceDir, setSourceDir] = useState(summary?.default_snapshot_dir ?? "");
  const [isBusy, setIsBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const assetCards = useMemo(() => summary?.asset_count_cards ?? [], [summary]);
  const reviewCards = useMemo(() => summary?.review_status_cards ?? [], [summary]);
  const stageCards = useMemo(() => summary?.stage_distribution_cards ?? [], [summary]);

  useEffect(() => {
    if (!sourceDir && summary?.default_snapshot_dir) {
      setSourceDir(summary.default_snapshot_dir);
    }
  }, [sourceDir, summary?.default_snapshot_dir]);

  async function handleImport() {
    setIsBusy(true);
    setError(null);
    setMessage(null);
    try {
      await importSnapshot(token, sourceDir, true);
      setMessage("快照导入成功，已激活为当前数据视图。");
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "导入失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleActivate(snapshotId: string) {
    setIsBusy(true);
    setError(null);
    setMessage(null);
    try {
      await activateSnapshot(token, snapshotId);
      setMessage("已切换激活快照。");
      await onRefresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "激活失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleExport() {
    setIsBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await exportReviewedEpisodes(token, summary?.active_snapshot?.snapshot_id);
      const blob = new Blob([JSON.stringify(result.items, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `reviewed_episodes_${result.snapshot_id}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("已导出 reviewed episodes。");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "导出失败");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero panel-accent">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h2>当前知识数据库概览</h2>
          <p className="muted-text">
            激活快照：{summary?.active_snapshot?.snapshot_id ?? "未导入"} · 当前登录角色：{user.role_label}
          </p>
        </div>
        <div className="hero-actions">
          <button className="ghost-button" onClick={onRefresh} type="button">
            刷新数据
          </button>
          <button className="primary-button" onClick={handleExport} type="button">
            导出审核后 Episode
          </button>
        </div>
      </section>

      {message ? <div className="success-banner">{message}</div> : null}
      {error ? <div className="error-banner">{error}</div> : null}

      <div className="stats-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Assets</p>
              <h3>资产数量</h3>
            </div>
          </div>
          <div className="chip-grid">
            {assetCards.map((card) => (
              <div className="stat-card" key={card.key}>
                <strong>{card.count}</strong>
                <span className="stat-card-label">{card.label}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Reviews</p>
              <h3>审核状态</h3>
            </div>
          </div>
          <div className="chip-grid">
            {reviewCards.map((card) => (
              <div className="stat-card" key={card.key}>
                <strong>{card.count}</strong>
                <span className="stat-card-label">{card.label}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Stages</p>
              <h3>阶段分布</h3>
            </div>
          </div>
          <div className="chip-grid">
            {stageCards.map((card) => (
              <div className="stat-card" key={card.key} title={card.description ?? undefined}>
                <strong>{card.count}</strong>
                <span className="stat-card-label">{card.label}</span>
                {card.description ? <span className="stat-card-description">{card.description}</span> : null}
              </div>
            ))}
          </div>
        </section>
      </div>

      {user.role === "admin" ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Import</p>
              <h3>导入新快照</h3>
            </div>
          </div>
          <div className="inline-form">
            <input value={sourceDir} onChange={(event) => setSourceDir(event.target.value)} />
            <button className="primary-button" disabled={isBusy} onClick={handleImport} type="button">
              {isBusy ? "导入中..." : "导入并激活"}
            </button>
          </div>
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Snapshots</p>
            <h3>快照列表</h3>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>snapshot_id</th>
              <th>来源目录</th>
              <th>导入时间</th>
              <th>是否激活</th>
              <th>记录数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((snapshot) => (
              <tr key={snapshot.snapshot_id}>
                <td>{snapshot.snapshot_id}</td>
                <td className="truncate-cell">{snapshot.source_dir}</td>
                <td>{new Date(snapshot.imported_at).toLocaleString()}</td>
                <td>{snapshot.is_active ? "已激活" : "未激活"}</td>
                <td>{Object.values(snapshot.asset_counts).reduce((sum, value) => sum + value, 0)}</td>
                <td>
                  {user.role === "admin" ? (
                    <button
                      className="ghost-button small"
                      disabled={snapshot.is_active || isBusy}
                      onClick={() => handleActivate(snapshot.snapshot_id)}
                      type="button"
                    >
                      激活
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
