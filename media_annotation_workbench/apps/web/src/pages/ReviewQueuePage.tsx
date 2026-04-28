import { useEffect, useMemo, useState } from "react";

import {
  approveReviewTask,
  claimReviewTask,
  fetchReviewTaskDetail,
  fetchReviewTasks,
  returnReviewTask,
  saveReviewDraft,
  submitReviewTask,
} from "../lib/api";
import type { KeyLabelOption, ReviewTaskDetail, ReviewTaskListItem, TraitItem, UserInfo } from "../lib/types";
import { EvidenceChatTimeline } from "../components/EvidenceChatTimeline";
import { JsonPanel } from "../components/JsonPanel";
import { TraitEditor } from "../components/TraitEditor";

interface ReviewQueuePageProps {
  token: string;
  user: UserInfo;
  activeSnapshotId?: string;
}

const reviewStatusOptions = [
  { key: "", label: "全部状态" },
  { key: "pending", label: "待审核" },
  { key: "in_progress", label: "审核中" },
  { key: "submitted", label: "待管理员审核" },
  { key: "approved", label: "已通过" },
  { key: "returned", label: "已退回" },
];

const diffFieldLabels: Record<string, string> = {
  workflow_stage: "流程阶段",
  episode_goal: "片段目标",
  objection_type: "阻力类型",
  outcome: "结果",
  confidence: "置信度",
};

function toTraitItems(value: unknown): TraitItem[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value as TraitItem[];
}

function getOptions(detail: ReviewTaskDetail | null, fieldName: string): KeyLabelOption[] {
  return detail?.field_options?.[fieldName] ?? [];
}

function asText(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function ReviewQueuePage({ token, user, activeSnapshotId }: ReviewQueuePageProps) {
  const [items, setItems] = useState<ReviewTaskListItem[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ReviewTaskDetail | null>(null);
  const [search, setSearch] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [creatorId, setCreatorId] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [workflowStage, setWorkflowStage] = useState("");
  const [episodeGoal, setEpisodeGoal] = useState("");
  const [objectionType, setObjectionType] = useState("");
  const [outcome, setOutcome] = useState("");
  const [confidence, setConfidence] = useState("0.8");
  const [reviewNotes, setReviewNotes] = useState("");
  const [traits, setTraits] = useState<TraitItem[]>([]);

  async function loadTasks() {
    setIsBusy(true);
    setError(null);
    try {
      const response = await fetchReviewTasks(token, {
        snapshot_id: activeSnapshotId,
        search,
        review_status: reviewStatus,
        creator_id: creatorId,
      });
      setItems(response.items);
      if (!selectedTaskId && response.items[0]) {
        setSelectedTaskId(response.items[0].review_task_id);
      }
      if (selectedTaskId && !response.items.some((item) => item.review_task_id === selectedTaskId)) {
        setSelectedTaskId(response.items[0]?.review_task_id ?? null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "加载审核队列失败");
    } finally {
      setIsBusy(false);
    }
  }

  async function loadDetail(reviewTaskId: string) {
    setIsBusy(true);
    setError(null);
    try {
      const response = await fetchReviewTaskDetail(token, reviewTaskId);
      const reviewedEpisode = (response.reviewed_episode ?? {}) as Record<string, unknown>;
      const latestEdit = (response.latest_edit ?? {}) as Record<string, unknown>;
      setDetail(response);
      setWorkflowStage(String(reviewedEpisode.workflow_stage ?? ""));
      setEpisodeGoal(String(reviewedEpisode.episode_goal ?? ""));
      setObjectionType(String(reviewedEpisode.objection_type ?? ""));
      setOutcome(String(reviewedEpisode.outcome ?? ""));
      setConfidence(String(reviewedEpisode.confidence ?? 0.8));
      setReviewNotes(String(latestEdit.review_notes ?? ""));
      setTraits(toTraitItems(reviewedEpisode.creator_traits));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "加载任务详情失败");
    } finally {
      setIsBusy(false);
    }
  }

  useEffect(() => {
    if (activeSnapshotId) {
      void loadTasks();
    }
  }, [activeSnapshotId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selectedTaskId) {
      void loadDetail(selectedTaskId);
    }
  }, [selectedTaskId]); // eslint-disable-line react-hooks/exhaustive-deps

  const diffRows = useMemo(() => {
    const rawEpisode = (detail?.raw_episode ?? {}) as Record<string, unknown>;
    const reviewedEpisode = (detail?.reviewed_episode ?? {}) as Record<string, unknown>;
    const keys = ["workflow_stage", "episode_goal", "objection_type", "outcome", "confidence"];
    return keys.map((key) => ({
      key,
      label: diffFieldLabels[key] ?? key,
      raw: rawEpisode[key],
      reviewed: reviewedEpisode[key],
      changed: rawEpisode[key] !== reviewedEpisode[key],
    }));
  }, [detail]);

  async function handleMutation(action: () => Promise<void>, successMessage: string) {
    setIsBusy(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
      await loadTasks();
      if (selectedTaskId) {
        await loadDetail(selectedTaskId);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "操作失败");
    } finally {
      setIsBusy(false);
    }
  }

  const workflowStageOptions = getOptions(detail, "workflow_stage");
  const episodeGoalOptions = getOptions(detail, "episode_goal");
  const objectionTypeOptions = getOptions(detail, "objection_type");
  const outcomeOptions = getOptions(detail, "outcome");

  return (
    <div className="review-layout">
      <section className="panel review-list-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Review Queue</p>
            <h2>审核任务</h2>
          </div>
          <button className="ghost-button small" onClick={() => void loadTasks()} type="button">
            刷新
          </button>
        </div>

        <div className="filter-grid compact">
          <input placeholder="关键词搜索" value={search} onChange={(event) => setSearch(event.target.value)} />
          <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
            {reviewStatusOptions.map((option) => (
              <option key={option.key || "all"} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
          <input placeholder="达人ID" value={creatorId} onChange={(event) => setCreatorId(event.target.value)} />
          <button className="primary-button" disabled={isBusy} onClick={() => void loadTasks()} type="button">
            查询
          </button>
        </div>

        <div className="review-list">
          {items.map((item) => (
            <button
              key={item.review_task_id}
              className={`review-item ${selectedTaskId === item.review_task_id ? "review-item-active" : ""}`}
              onClick={() => setSelectedTaskId(item.review_task_id)}
              type="button"
            >
              <strong>{item.raw_review_id}</strong>
              <span>{item.workflow_stage_label ?? item.workflow_stage ?? "未标注阶段"}</span>
              <span>{item.episode_goal_label ?? item.episode_goal ?? "未标注目标"}</span>
              <span>{item.status_label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="panel review-detail-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Review Detail</p>
            <h2>{detail?.task.raw_review_id ?? "请选择任务"}</h2>
          </div>
          <div className="button-row">
            {detail && user.role !== "viewer" ? (
              <button
                className="ghost-button small"
                onClick={() =>
                  void handleMutation(
                    () => claimReviewTask(token, detail.task.review_task_id).then(() => undefined),
                    "已领取任务。",
                  )
                }
                type="button"
              >
                领取任务
              </button>
            ) : null}
          </div>
        </div>

        {message ? <div className="success-banner">{message}</div> : null}
        {error ? <div className="error-banner">{error}</div> : null}

        {!detail ? (
          <p className="muted-text">从左侧选择一个审核任务开始。</p>
        ) : (
          <>
            <div className="review-summary">
              <div className="summary-chip">审核状态：{detail.task.status_label}</div>
              <div className="summary-chip">优先级：{detail.task.priority_label}</div>
              <div className="summary-chip">达人：{detail.task.creator_id ?? "—"}</div>
              <div className="summary-chip">片段：{detail.task.episode_id}</div>
            </div>

            <section className="panel inset-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Diff</p>
                  <h3>原始值与审核后对比</h3>
                </div>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>原始值</th>
                    <th>审核后</th>
                  </tr>
                </thead>
                <tbody>
                  {diffRows.map((row) => (
                    <tr className={row.changed ? "changed-row" : ""} key={row.key}>
                      <td>{row.label}</td>
                      <td>{asText(row.raw)}</td>
                      <td>{asText(row.reviewed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="panel inset-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Edit</p>
                  <h3>人工修订</h3>
                </div>
              </div>

              <div className="filter-grid">
                <label className="field-block">
                  <span>流程阶段</span>
                  <select value={workflowStage} onChange={(event) => setWorkflowStage(event.target.value)}>
                    <option value="">请选择流程阶段</option>
                    {workflowStageOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-block">
                  <span>片段目标</span>
                  <select value={episodeGoal} onChange={(event) => setEpisodeGoal(event.target.value)}>
                    <option value="">请选择片段目标</option>
                    {episodeGoalOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-block">
                  <span>阻力类型</span>
                  <select value={objectionType} onChange={(event) => setObjectionType(event.target.value)}>
                    <option value="">请选择阻力类型</option>
                    {objectionTypeOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-block">
                  <span>结果</span>
                  <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
                    <option value="">请选择结果</option>
                    {outcomeOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-block">
                  <span>置信度</span>
                  <input type="number" max={1} min={0} step={0.01} value={confidence} onChange={(event) => setConfidence(event.target.value)} />
                </label>
              </div>

              <label className="field-block">
                <span>审核备注</span>
                <textarea rows={4} value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} />
              </label>

              <TraitEditor value={traits} onChange={setTraits} />

              <div className="button-row">
                {user.role !== "viewer" ? (
                  <button
                    className="primary-button"
                    disabled={isBusy}
                    onClick={() =>
                      void handleMutation(
                        () =>
                          saveReviewDraft(token, detail.task.review_task_id, {
                            workflow_stage: workflowStage,
                            episode_goal: episodeGoal,
                            objection_type: objectionType,
                            outcome,
                            confidence: Number(confidence),
                            review_notes: reviewNotes,
                            creator_traits: traits,
                            review_status: "in_progress",
                          }).then(() => undefined),
                        "草稿已保存。",
                      )
                    }
                    type="button"
                  >
                    保存草稿
                  </button>
                ) : null}

                {user.role !== "viewer" ? (
                  <button
                    className="ghost-button"
                    disabled={isBusy}
                    onClick={() =>
                      void handleMutation(
                        async () => {
                          await saveReviewDraft(token, detail.task.review_task_id, {
                            workflow_stage: workflowStage,
                            episode_goal: episodeGoal,
                            objection_type: objectionType,
                            outcome,
                            confidence: Number(confidence),
                            review_notes: reviewNotes,
                            creator_traits: traits,
                            review_status: "in_progress",
                          });
                          await submitReviewTask(token, detail.task.review_task_id, reviewNotes);
                        },
                        "任务已提交审核。",
                      )
                    }
                    type="button"
                  >
                    提交审核
                  </button>
                ) : null}

                {user.role === "admin" ? (
                  <button
                    className="ghost-button"
                    disabled={isBusy}
                    onClick={() =>
                      void handleMutation(
                        () => approveReviewTask(token, detail.task.review_task_id, reviewNotes).then(() => undefined),
                        "任务已通过。",
                      )
                    }
                    type="button"
                  >
                    管理员通过
                  </button>
                ) : null}

                {user.role === "admin" ? (
                  <button
                    className="ghost-button danger"
                    disabled={isBusy}
                    onClick={() =>
                      void handleMutation(
                        () => returnReviewTask(token, detail.task.review_task_id, reviewNotes).then(() => undefined),
                        "任务已退回。",
                      )
                    }
                    type="button"
                  >
                    管理员退回
                  </button>
                ) : null}
              </div>
            </section>

            <div className="two-column-grid">
              <JsonPanel title="原始审核队列记录" value={detail.raw_review_item} />
              <section className="panel inset-panel">
                <div className="panel-header">
                  <div>
                    <p className="eyebrow">Evidence Chat</p>
                    <h3>证据消息时间线</h3>
                  </div>
                </div>
                <EvidenceChatTimeline messages={detail.evidence_chat_messages} />
              </section>
            </div>

            <section className="panel inset-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Timeline</p>
                  <h3>审核日志</h3>
                </div>
              </div>
              <div className="timeline-list">
                {detail.events.map((event) => (
                  <div className="timeline-item" key={event.event_id}>
                    <strong>{event.event_type_label}</strong>
                    <span>{new Date(event.created_at).toLocaleString()}</span>
                    <p className="muted-text">{event.note ?? "—"}</p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </section>
    </div>
  );
}
