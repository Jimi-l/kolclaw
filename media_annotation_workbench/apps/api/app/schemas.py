from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Role = Literal["admin", "annotator", "viewer"]


class UserInfo(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: Role
    role_label: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class ImportRequest(BaseModel):
    source_dir: str
    activate: bool = True


class SnapshotResponse(BaseModel):
    snapshot_id: str
    source_dir: str
    imported_at: datetime
    is_active: bool
    asset_counts: dict[str, int]
    file_hashes: dict[str, str]


class ImportResponse(BaseModel):
    snapshot: SnapshotResponse
    imported_assets: dict[str, int]


class DashboardSummaryResponse(BaseModel):
    active_snapshot: SnapshotResponse | None
    asset_counts: dict[str, int]
    review_counts: dict[str, int]
    stage_distribution: dict[str, int]
    asset_count_cards: list[dict[str, Any]]
    review_status_cards: list[dict[str, Any]]
    stage_distribution_cards: list[dict[str, Any]]
    recent_imports: list[SnapshotResponse]
    usage_groups: dict[str, list[str]]
    default_snapshot_dir: str


class AssetListResponse(BaseModel):
    asset_type: str
    asset_type_label: str | None = None
    snapshot_id: str
    view: str
    total: int
    offset: int
    limit: int
    items: list[dict[str, Any]]


class AssetDetailResponse(BaseModel):
    asset_type: str
    asset_type_label: str | None = None
    snapshot_id: str
    view: str
    raw_item: dict[str, Any] | None = None
    reviewed_item: dict[str, Any] | None = None
    review_status: str | None = None
    related: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    document_content: str | None = None
    document_format: str | None = None


class ReviewTaskListItem(BaseModel):
    review_task_id: str
    raw_review_id: str
    snapshot_id: str
    episode_id: str
    conversation_id: str | None = None
    creator_id: str | None = None
    priority: str
    priority_label: str
    status: str
    status_label: str
    workflow_stage: str | None = None
    workflow_stage_label: str | None = None
    episode_goal: str | None = None
    episode_goal_label: str | None = None
    objection_type: str | None = None
    objection_type_label: str | None = None
    assigned_user: UserInfo | None = None
    updated_at: datetime


class ReviewEventResponse(BaseModel):
    event_id: str
    event_type: str
    event_type_label: str
    note: str | None = None
    payload: dict[str, Any]
    created_at: datetime
    actor: UserInfo | None = None


class EvidenceChatMessage(BaseModel):
    message_id: str
    seq_num: int | None = None
    role: str | None = None
    role_label: str | None = None
    speaker_name: str
    speaker_badge: str
    formatted_time: str | None = None
    clean_text: str
    raw_text: str
    is_direct_evidence: bool
    creator_aliases: list[str] = Field(default_factory=list)
    media_name: str | None = None


class KeyLabelOption(BaseModel):
    key: str
    label: str
    description: str | None = None


class ReviewTaskDetailResponse(BaseModel):
    task: ReviewTaskListItem
    raw_review_item: dict[str, Any]
    raw_episode: dict[str, Any] | None = None
    reviewed_episode: dict[str, Any] | None = None
    latest_edit: dict[str, Any] | None = None
    evidence_messages: list[dict[str, Any]] = Field(default_factory=list)
    evidence_chat_messages: list[EvidenceChatMessage] = Field(default_factory=list)
    related_assets: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    display_labels: dict[str, str | None] = Field(default_factory=dict)
    field_options: dict[str, list[KeyLabelOption]] = Field(default_factory=dict)
    events: list[ReviewEventResponse] = Field(default_factory=list)


class ReviewTaskListResponse(BaseModel):
    snapshot_id: str
    total: int
    items: list[ReviewTaskListItem]


class ReviewDraftUpdateRequest(BaseModel):
    workflow_stage: str | None = None
    episode_goal: str | None = None
    objection_type: str | None = None
    creator_traits: list[dict[str, Any]] | None = None
    outcome: str | None = None
    confidence: float | None = None
    review_notes: str | None = None
    review_status: str | None = None


class ReviewActionRequest(BaseModel):
    review_notes: str | None = None


class ReviewMutationResponse(BaseModel):
    task: ReviewTaskListItem
    latest_edit: dict[str, Any] | None = None
    events: list[ReviewEventResponse]


class DocumentResponse(BaseModel):
    snapshot_id: str
    doc_type: str
    content: str
    format: str


class ReviewedEpisodesExportResponse(BaseModel):
    snapshot_id: str
    total: int
    items: list[dict[str, Any]]
