import type {
  AssetDetailResponse,
  AssetListResponse,
  DashboardSummary,
  DocumentResponse,
  LoginResponse,
  ReviewMutationResponse,
  ReviewTaskDetail,
  ReviewTaskListResponse,
  ReviewedEpisodesExportResponse,
  Snapshot,
  UserInfo,
  ViewMode,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function login(username: string, password: string) {
  return request<LoginResponse>("/api/auth/login", undefined, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function fetchCurrentUser(token: string) {
  return request<UserInfo>("/api/auth/me", token);
}

export function fetchDashboardSummary(token: string) {
  return request<DashboardSummary>("/api/dashboard/summary", token);
}

export function fetchSnapshots(token: string) {
  return request<Snapshot[]>("/api/snapshots", token);
}

export function importSnapshot(token: string, sourceDir: string, activate = true) {
  return request<{ snapshot: Snapshot; imported_assets: Record<string, number> }>("/api/imports", token, {
    method: "POST",
    body: JSON.stringify({ source_dir: sourceDir, activate }),
  });
}

export function activateSnapshot(token: string, snapshotId: string) {
  return request<Snapshot>(`/api/snapshots/${snapshotId}/activate`, token, {
    method: "POST",
  });
}

export function fetchAssets(token: string, assetType: string, params: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    query.set(key, String(value));
  });
  return request<AssetListResponse>(`/api/assets/${assetType}?${query.toString()}`, token);
}

export function fetchAssetDetail(token: string, assetType: string, itemId: string, view: ViewMode, snapshotId?: string) {
  const query = new URLSearchParams({ view });
  if (snapshotId) {
    query.set("snapshot_id", snapshotId);
  }
  return request<AssetDetailResponse>(`/api/assets/${assetType}/${itemId}?${query.toString()}`, token);
}

export function fetchReviewTasks(token: string, params: Record<string, string | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (!value) {
      return;
    }
    query.set(key, value);
  });
  return request<ReviewTaskListResponse>(`/api/reviews/tasks?${query.toString()}`, token);
}

export function fetchReviewTaskDetail(token: string, reviewTaskId: string) {
  return request<ReviewTaskDetail>(`/api/reviews/tasks/${reviewTaskId}`, token);
}

export function claimReviewTask(token: string, reviewTaskId: string) {
  return request<ReviewMutationResponse>(`/api/reviews/tasks/${reviewTaskId}/claim`, token, {
    method: "POST",
  });
}

export function saveReviewDraft(token: string, reviewTaskId: string, payload: Record<string, unknown>) {
  return request<ReviewMutationResponse>(`/api/reviews/tasks/${reviewTaskId}/draft`, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitReviewTask(token: string, reviewTaskId: string, reviewNotes?: string) {
  return request<ReviewMutationResponse>(`/api/reviews/tasks/${reviewTaskId}/submit`, token, {
    method: "POST",
    body: JSON.stringify({ review_notes: reviewNotes ?? "" }),
  });
}

export function approveReviewTask(token: string, reviewTaskId: string, reviewNotes?: string) {
  return request<ReviewMutationResponse>(`/api/reviews/tasks/${reviewTaskId}/approve`, token, {
    method: "POST",
    body: JSON.stringify({ review_notes: reviewNotes ?? "" }),
  });
}

export function returnReviewTask(token: string, reviewTaskId: string, reviewNotes?: string) {
  return request<ReviewMutationResponse>(`/api/reviews/tasks/${reviewTaskId}/return`, token, {
    method: "POST",
    body: JSON.stringify({ review_notes: reviewNotes ?? "" }),
  });
}

export function fetchDocument(token: string, docType: string, snapshotId?: string) {
  const query = new URLSearchParams();
  if (snapshotId) {
    query.set("snapshot_id", snapshotId);
  }
  return request<DocumentResponse>(`/api/docs/${docType}?${query.toString()}`, token);
}

export function exportReviewedEpisodes(token: string, snapshotId?: string) {
  const query = new URLSearchParams();
  if (snapshotId) {
    query.set("snapshot_id", snapshotId);
  }
  return request<ReviewedEpisodesExportResponse>(`/api/exports/reviewed-episodes?${query.toString()}`, token);
}
