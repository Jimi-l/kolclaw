import type {
  BriefStructureResponse,
  CampaignBrief,
  CandidatesRunResponse,
  RetrievalPlan,
  StrategyTemplate,
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
