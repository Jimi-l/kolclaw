import { useEffect, useMemo, useState } from "react";

import { fetchAssetDetail, fetchAssets, fetchDocument } from "../lib/api";
import type { AssetDetailResponse, AssetListResponse, DashboardSummary, ViewMode } from "../lib/types";
import { DetailDrawer } from "../components/DetailDrawer";

const usageOptions = [
  { key: "brief_cards", label: "按用途 · Brief 知识库" },
  { key: "negotiation_episodes", label: "按用途 · 谈判知识库" },
  { key: "talk_templates", label: "按用途 · 话术模板库" },
  { key: "workflow_playbook", label: "按用途 · 履约 SOP" },
  { key: "retrieval_chunks", label: "按用途 · 检索切片" },
  { key: "gold_episode_review_queue", label: "按用途 · 审核队列" },
  { key: "asset_field_guide", label: "按用途 · 字段说明" },
];

const fileOptions = [
  { key: "conversation_messages", label: "conversation_messages.jsonl" },
  { key: "brief_cards", label: "brief_cards.jsonl" },
  { key: "negotiation_episodes", label: "negotiation_episodes.jsonl" },
  { key: "talk_templates", label: "talk_templates.jsonl" },
  { key: "workflow_playbook", label: "workflow_playbook.jsonl" },
  { key: "retrieval_chunks", label: "retrieval_chunks.jsonl" },
  { key: "gold_episode_review_queue", label: "gold_episode_review_queue.jsonl" },
  { key: "tag_dictionary", label: "tag_dictionary.yaml" },
  { key: "annotation_guideline", label: "annotation_guideline.md" },
  { key: "asset_field_guide", label: "asset_field_guide.md" },
];

const documentKeys = new Set(["tag_dictionary", "annotation_guideline", "asset_field_guide"]);

interface AssetBrowserPageProps {
  token: string;
  summary: DashboardSummary | null;
}

export function AssetBrowserPage({ token, summary }: AssetBrowserPageProps) {
  const [browserMode, setBrowserMode] = useState<"usage" | "file">("usage");
  const [selectedAsset, setSelectedAsset] = useState<string>("brief_cards");
  const [viewMode, setViewMode] = useState<ViewMode>("reviewed");
  const [search, setSearch] = useState("");
  const [workflowStage, setWorkflowStage] = useState("");
  const [episodeGoal, setEpisodeGoal] = useState("");
  const [objectionType, setObjectionType] = useState("");
  const [creatorId, setCreatorId] = useState("");
  const [knowledgeBase, setKnowledgeBase] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [assetResponse, setAssetResponse] = useState<AssetListResponse | null>(null);
  const [documentDetail, setDocumentDetail] = useState<AssetDetailResponse | null>(null);
  const [drawerDetail, setDrawerDetail] = useState<AssetDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const options = browserMode === "usage" ? usageOptions : fileOptions;
  const activeSnapshotId = summary?.active_snapshot?.snapshot_id;

  useEffect(() => {
    const firstOption = options[0];
    if (!options.some((option) => option.key === selectedAsset) && firstOption) {
      setSelectedAsset(firstOption.key);
    }
  }, [browserMode]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadAssetData(assetType: string) {
    setIsBusy(true);
    setError(null);
    setDrawerDetail(null);
    try {
      if (documentKeys.has(assetType)) {
        const document = await fetchDocument(token, assetType, activeSnapshotId);
        setDocumentDetail({
          asset_type: assetType,
          snapshot_id: document.snapshot_id,
          view: "raw",
          raw_item: null,
          reviewed_item: null,
          review_status: null,
          related: {},
          document_content: document.content,
          document_format: document.format,
        });
        setAssetResponse(null);
        return;
      }

      const response = await fetchAssets(token, assetType, {
        snapshot_id: activeSnapshotId,
        view: viewMode,
        search,
        workflow_stage: workflowStage,
        episode_goal: episodeGoal,
        objection_type: objectionType,
        creator_id: creatorId,
        knowledge_base: knowledgeBase,
        review_status: reviewStatus,
        limit: 50,
      });
      setAssetResponse(response);
      setDocumentDetail(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "加载资产失败");
    } finally {
      setIsBusy(false);
    }
  }

  useEffect(() => {
    if (!selectedAsset || !activeSnapshotId) {
      return;
    }
    void loadAssetData(selectedAsset);
  }, [selectedAsset, activeSnapshotId, viewMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = assetResponse?.items ?? [];
  const columns = useMemo(() => {
    const firstRow = rows[0];
    return firstRow ? Object.keys(firstRow).slice(0, 8) : [];
  }, [rows]);

  async function handleSearch() {
    await loadAssetData(selectedAsset);
  }

  async function handleOpenDetail(item: Record<string, unknown>) {
    const idFieldMap: Record<string, string> = {
      conversation_messages: "message_id",
      brief_cards: "brief_card_id",
      negotiation_episodes: "episode_id",
      talk_templates: "template_id",
      workflow_playbook: "step_id",
      retrieval_chunks: "chunk_id",
      gold_episode_review_queue: "review_id",
    };
    const idField = idFieldMap[selectedAsset];
    if (!idField) {
      return;
    }
    const itemId = item[idField];
    if (typeof itemId !== "string") {
      return;
    }
    setIsBusy(true);
    try {
      const detail = await fetchAssetDetail(token, selectedAsset, itemId, viewMode, activeSnapshotId);
      setDrawerDetail(detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "详情加载失败");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Asset Browser</p>
            <h2>数据库浏览</h2>
          </div>
          <div className="button-row">
            <button
              className={`ghost-button small ${browserMode === "usage" ? "is-selected" : ""}`}
              onClick={() => setBrowserMode("usage")}
              type="button"
            >
              按用途看
            </button>
            <button
              className={`ghost-button small ${browserMode === "file" ? "is-selected" : ""}`}
              onClick={() => setBrowserMode("file")}
              type="button"
            >
              按文件看
            </button>
          </div>
        </div>

        <div className="selector-grid">
          {options.map((option) => (
            <button
              key={option.key}
              className={`selector-chip ${selectedAsset === option.key ? "selector-chip-active" : ""}`}
              onClick={() => setSelectedAsset(option.key)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Filters</p>
            <h3>搜索与过滤</h3>
          </div>
          {!documentKeys.has(selectedAsset) ? (
            <div className="button-row">
              <button
                className={`ghost-button small ${viewMode === "reviewed" ? "is-selected" : ""}`}
                onClick={() => setViewMode("reviewed")}
                type="button"
              >
                reviewed view
              </button>
              <button
                className={`ghost-button small ${viewMode === "raw" ? "is-selected" : ""}`}
                onClick={() => setViewMode("raw")}
                type="button"
              >
                raw view
              </button>
            </div>
          ) : null}
        </div>

        {!documentKeys.has(selectedAsset) ? (
          <div className="filter-grid">
            <input placeholder="关键词搜索" value={search} onChange={(event) => setSearch(event.target.value)} />
            <input placeholder="workflow_stage" value={workflowStage} onChange={(event) => setWorkflowStage(event.target.value)} />
            <input placeholder="episode_goal" value={episodeGoal} onChange={(event) => setEpisodeGoal(event.target.value)} />
            <input placeholder="objection_type" value={objectionType} onChange={(event) => setObjectionType(event.target.value)} />
            <input placeholder="creator_id" value={creatorId} onChange={(event) => setCreatorId(event.target.value)} />
            <input placeholder="knowledge_base" value={knowledgeBase} onChange={(event) => setKnowledgeBase(event.target.value)} />
            <input placeholder="review_status" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)} />
            <button className="primary-button" disabled={isBusy} onClick={handleSearch} type="button">
              {isBusy ? "加载中..." : "查询"}
            </button>
          </div>
        ) : null}

        {error ? <div className="error-banner">{error}</div> : null}

        {documentDetail?.document_content ? (
          <pre className="doc-panel">{documentDetail.document_content}</pre>
        ) : (
          <div className="table-shell">
            <div className="table-toolbar">
              <span className="muted-text">
                snapshot_id: {assetResponse?.snapshot_id ?? activeSnapshotId ?? "—"} · total: {assetResponse?.total ?? 0}
              </span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  {columns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr className="clickable-row" key={`${selectedAsset}-${index}`} onClick={() => void handleOpenDetail(row)}>
                    {columns.map((column) => (
                      <td key={column} className="truncate-cell">
                        {typeof row[column] === "object" ? JSON.stringify(row[column]) : String(row[column] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {drawerDetail ? (
        <DetailDrawer
          title={drawerDetail.asset_type}
          subtitle={`snapshot_id: ${drawerDetail.snapshot_id}`}
          rawItem={drawerDetail.raw_item}
          reviewedItem={drawerDetail.reviewed_item}
          related={drawerDetail.related}
          content={drawerDetail.document_content}
          format={drawerDetail.document_format}
          onClose={() => setDrawerDetail(null)}
        />
      ) : null}
    </div>
  );
}
