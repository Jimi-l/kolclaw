from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from search_agent.enums import AnalysisStatus, NextAction, RecordStatus, TrafficTrend
from search_agent.models.common import CommentSnippet


class CreatorDiscoveryRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    workflow_run_id: str | None = None
    source_stage: Literal["creator-discovery"] = "creator-discovery"
    platform: Literal["douyin"] = "douyin"
    status: RecordStatus

    collection_date: str | None = None
    video_url: str | None = None
    video_url_capture_source: Literal["network", "dom", "none"] | None = None
    publish_time_raw: str | None = None
    publish_date_normalized: str | None = None
    hotness_age_score: str | None = None
    total_interaction_text: str | None = None
    like_count_raw: str | None = None
    comment_count_raw: str | None = None
    favorite_count_raw: str | None = None
    share_count_raw: str | None = None
    ai_generated_flag: bool | None = None
    active_text_summary: str | None = None
    video_title_text: str | None = None
    video_description_raw: str | None = None
    expanded_description_text: str | None = None
    video_text_bundle: str | None = None
    chapter_texts: list[str] = Field(default_factory=list)
    related_search_terms: list[str] = Field(default_factory=list)
    author_statement_texts: list[str] = Field(default_factory=list)
    visible_subtitle_segments: list[str] = Field(default_factory=list)
    top_comments: list[CommentSnippet] = Field(default_factory=list)
    top_comments_source: Literal["network", "ui", "mixed", "none"] | None = None
    comment_collection_status: Literal["success", "panel_open_failed", "network_miss", "panel_empty", "parse_failed"] | None = None
    comment_collection_debug: str | None = None
    keyframe_paths: list[str] = Field(default_factory=list)

    creator_name: str | None = None
    follower_count_raw: str | None = None
    follower_count_normalized: int | None = None
    total_liked_count_raw: str | None = None
    profile_bio: str | None = None
    recommendation_video_position: str | None = None
    recent_video_titles: list[str] = Field(default_factory=list)
    visible_scenes: list[str] = Field(default_factory=list)
    speaking_style: str | None = None
    video_duration_pattern: str | None = None

    recommendation_video_like_raw: str | None = None
    recent_video_like_1_raw: str | None = None
    recent_video_like_2_raw: str | None = None
    recent_video_like_3_raw: str | None = None
    recent_3_avg_like_raw: str | None = None
    traffic_trend: TrafficTrend | None = None
    traffic_trend_reason: str | None = None

    content_taxonomy_path: list[str] = Field(default_factory=list)
    content_leaf_tags: list[str] = Field(default_factory=list)
    profession_tags: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    life_tags: list[str] = Field(default_factory=list)
    appearance_relation_tags: list[str] = Field(default_factory=list)
    monetization: list[str] = Field(default_factory=list)
    cooperate_type: str | None = None
    analysis_status: AnalysisStatus | None = None
    analysis_backend: str | None = None
    analysis_model: str | None = None
    video_content_summary: str | None = None
    content_analysis_reasoning: str | None = None
    tagging_reasoning: str | None = None
    analysis_error: str | None = None

    notes: str | None = None
    duplicate_key: str
    next_action: NextAction

    def is_ready_for_xingtu(self) -> bool:
        required_fields = (
            self.platform,
            self.creator_name,
            self.video_url,
            self.collection_date,
            self.total_interaction_text,
            self.follower_count_raw,
            self.content_leaf_tags or self.content_taxonomy_path,
        )
        return all(required_fields)

    @model_validator(mode="after")
    def validate_record(self) -> "CreatorDiscoveryRecord":
        if len(self.content_taxonomy_path) > 4:
            raise ValueError("content_taxonomy_path must contain at most 4 items")
        if len(self.visible_subtitle_segments) > 6:
            raise ValueError("visible_subtitle_segments must contain at most 6 items")
        if len(self.keyframe_paths) > 8:
            raise ValueError("keyframe_paths must contain at most 8 items")
        if self.status == RecordStatus.QUEUED_FOR_XINGTU:
            if self.next_action != NextAction.QUEUE_FOR_XINGTU:
                raise ValueError("queued_for_xingtu records must use next_action=queue_for_xingtu")
            if not self.is_ready_for_xingtu():
                raise ValueError("queued_for_xingtu records must contain the minimum qualifying fields")
        if self.status == RecordStatus.SKIPPED and self.next_action not in {NextAction.SKIP, NextAction.MANUAL_REVIEW}:
            raise ValueError("skipped records must use skip or manual_review next_action")
        if self.status == RecordStatus.BLOCKED and self.next_action != NextAction.MANUAL_REVIEW:
            raise ValueError("blocked discovery records must use next_action=manual_review")
        return self
