export type Role = "admin" | "annotator" | "viewer";
export type ViewMode = "raw" | "reviewed";

export interface UserInfo {
  user_id: string;
  username: string;
  display_name: string;
  role: Role;
  role_label: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export interface Snapshot {
  snapshot_id: string;
  source_dir: string;
  imported_at: string;
  is_active: boolean;
  asset_counts: Record<string, number>;
  file_hashes: Record<string, string>;
}

export interface DashboardSummary {
  active_snapshot: Snapshot | null;
  asset_counts: Record<string, number>;
  review_counts: Record<string, number>;
  stage_distribution: Record<string, number>;
  asset_count_cards: Array<{ key: string; label: string; count: number }>;
  review_status_cards: Array<{ key: string; label: string; count: number }>;
  stage_distribution_cards: Array<{ key: string; label: string; description?: string | null; count: number }>;
  recent_imports: Snapshot[];
  usage_groups: Record<string, string[]>;
  default_snapshot_dir: string;
}

export interface AssetListResponse {
  asset_type: string;
  asset_type_label?: string | null;
  snapshot_id: string;
  view: ViewMode;
  total: number;
  offset: number;
  limit: number;
  items: Record<string, unknown>[];
}

export interface AssetDetailResponse {
  asset_type: string;
  asset_type_label?: string | null;
  snapshot_id: string;
  view: ViewMode;
  raw_item: Record<string, unknown> | null;
  reviewed_item: Record<string, unknown> | null;
  review_status: string | null;
  related: Record<string, Record<string, unknown>[]>;
  document_content: string | null;
  document_format: string | null;
}

export interface ReviewTaskListItem {
  review_task_id: string;
  raw_review_id: string;
  snapshot_id: string;
  episode_id: string;
  conversation_id?: string | null;
  creator_id?: string | null;
  priority: string;
  priority_label: string;
  status: string;
  status_label: string;
  workflow_stage?: string | null;
  workflow_stage_label?: string | null;
  episode_goal?: string | null;
  episode_goal_label?: string | null;
  objection_type?: string | null;
  objection_type_label?: string | null;
  assigned_user?: UserInfo | null;
  updated_at: string;
}

export interface ReviewEvent {
  event_id: string;
  event_type: string;
  event_type_label: string;
  note?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  actor?: UserInfo | null;
}

export interface EvidenceChatMessage {
  message_id: string;
  seq_num?: number | null;
  role?: string | null;
  role_label?: string | null;
  speaker_name: string;
  speaker_badge: string;
  formatted_time?: string | null;
  clean_text: string;
  raw_text: string;
  is_direct_evidence: boolean;
  creator_aliases: string[];
  media_name?: string | null;
}

export interface KeyLabelOption {
  key: string;
  label: string;
  description?: string | null;
}

export interface ReviewTaskDetail {
  task: ReviewTaskListItem;
  raw_review_item: Record<string, unknown>;
  raw_episode: Record<string, unknown> | null;
  reviewed_episode: Record<string, unknown> | null;
  latest_edit: Record<string, unknown> | null;
  evidence_messages: Record<string, unknown>[];
  evidence_chat_messages: EvidenceChatMessage[];
  related_assets: Record<string, Record<string, unknown>[]>;
  display_labels: Record<string, string | null>;
  field_options: Record<string, KeyLabelOption[]>;
  events: ReviewEvent[];
}

export interface ReviewTaskListResponse {
  snapshot_id: string;
  total: number;
  items: ReviewTaskListItem[];
}

export interface ReviewMutationResponse {
  task: ReviewTaskListItem;
  latest_edit: Record<string, unknown> | null;
  events: ReviewEvent[];
}

export interface DocumentResponse {
  snapshot_id: string;
  doc_type: string;
  content: string;
  format: string;
}

export interface ReviewedEpisodesExportResponse {
  snapshot_id: string;
  total: number;
  items: Record<string, unknown>[];
}

export interface TraitItem {
  trait_name: string;
  value: string;
  confidence?: number;
  evidence_message_ids?: string[];
  rationale?: string;
}
