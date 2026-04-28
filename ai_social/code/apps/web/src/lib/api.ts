import type {
  BriefStructureResponse,
  CampaignBrief,
  CandidatesRunResponse,
  ExternalDocReferenceResponse,
  RetrievalPlan,
  ShortlistParseResponse,
  ShortlistPlanResponse,
  ShortlistRequirement,
  ShortlistRunResponse,
  StrategyTemplate,
  XingtuCpmAnalyzeResponse,
  XingtuCpmInput,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
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

export function fetchTemplates() {
  return request<StrategyTemplate[]>("/api/templates");
}

export function structureBrief(payload: { raw_text?: string; structured_draft?: CampaignBrief }) {
  return request<BriefStructureResponse>("/api/brief/structure", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function generateRetrievalPlan(payload: { brief: CampaignBrief; template_id: string }) {
  return request<RetrievalPlan>("/api/retrieval/plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runCandidates(payload: { brief: CampaignBrief; template_id: string; limit?: number }) {
  return request<CandidatesRunResponse>("/api/candidates/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchSample() {
  return request<CandidatesRunResponse>("/api/candidates/sample");
}

export function fetchShortlistReferences() {
  return request<ExternalDocReferenceResponse>("/api/shortlist/references");
}

export function parseShortlistBrief(payload: { raw_text?: string; structured_requirement?: ShortlistRequirement }) {
  return request<ShortlistParseResponse>("/api/shortlist/parse", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function previewShortlistPlan(payload: {
  raw_text?: string;
  structured_requirement?: ShortlistRequirement;
  collection_limit?: number;
  shortlist_limit?: number;
}) {
  return request<ShortlistPlanResponse>("/api/shortlist/plan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runShortlist(payload: {
  raw_text?: string;
  structured_requirement?: ShortlistRequirement;
  account_name?: string;
  storage_state_path?: string;
  collection_limit?: number;
  shortlist_limit?: number;
  headless?: boolean;
}) {
  return request<ShortlistRunResponse>("/api/shortlist/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchXingtuCpmSample() {
  return request<XingtuCpmAnalyzeResponse>("/api/xingtu-cpm/sample");
}

export function evaluateXingtuCpm(input: XingtuCpmInput) {
  return request<XingtuCpmAnalyzeResponse["assessment"]>("/api/xingtu-cpm/evaluate", {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export async function analyzeXingtuCpmFiles(files: File[]) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/api/xingtu-cpm/analyze`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return (await response.json()) as XingtuCpmAnalyzeResponse;
}

export type XingtuExtractionMode = "vlm_only";

export function analyzeXingtuCpmFilesWithMode(files: File[], mode: XingtuExtractionMode) {
  const endpointByMode: Record<XingtuExtractionMode, string> = {
    vlm_only: "/api/xingtu-cpm/analyze-vlm-only",
  };
  return uploadXingtuFiles(files, endpointByMode[mode]);
}

async function uploadXingtuFiles(files: File[], endpoint: string) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const url = `${API_BASE}${endpoint}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : String(caught);
    throw new Error(`上传请求失败：${message}。请求地址：${url}。请确认后端 127.0.0.1:8000 已启动，并从 127.0.0.1:5173 或 localhost:5173 打开页面。`);
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return (await response.json()) as XingtuCpmAnalyzeResponse;
}
