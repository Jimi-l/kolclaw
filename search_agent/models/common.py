from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from search_agent.enums import MatchConfidence, NextAction, WorkflowStage


class CustomTagLog(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tag_name: str
    tag_category: str
    reason: str


class CommentSnippet(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    author_name: str | None = None
    text: str
    like_count_raw: str | None = None
    source: Literal["network", "ui"]


class TaggingContext(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    creator_name: str | None = None
    profile_bio: str | None = None
    follower_count_raw: str | None = None
    total_liked_count_raw: str | None = None
    recommendation_video_summary: str | None = None
    video_description_raw: str | None = None
    video_title_text: str | None = None
    expanded_description_text: str | None = None
    video_text_bundle: str | None = None
    chapter_texts: list[str] = Field(default_factory=list)
    related_search_terms: list[str] = Field(default_factory=list)
    author_statement_texts: list[str] = Field(default_factory=list)
    recent_videos_summary: list[str] = Field(default_factory=list)
    visible_subtitle_segments: list[str] = Field(default_factory=list)
    top_comments: list[CommentSnippet] = Field(default_factory=list)
    visible_scenes: list[str] = Field(default_factory=list)
    speaking_style: str | None = None
    video_duration_pattern: str | None = None
    video_duration_seconds: int | None = None
    ai_generated_flag: bool | None = None
    extra_notes: str | None = None


class TaggingResult(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    content_taxonomy_path: list[str] = Field(default_factory=list)
    content_leaf_tags: list[str] = Field(default_factory=list)
    profession_tags: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    life_tags: list[str] = Field(default_factory=list)
    appearance_relation_tags: list[str] = Field(default_factory=list)
    monetization: list[str] = Field(default_factory=list)
    cooperate_type: str | None = None
    label_reasoning: str | None = None

    @field_validator("content_taxonomy_path")
    @classmethod
    def validate_taxonomy_depth(cls, value: list[str]) -> list[str]:
        if len(value) > 4:
            raise ValueError("content_taxonomy_path must contain at most 4 items")
        return value

    @field_validator(
        "content_leaf_tags",
        "profession_tags",
        "interest_tags",
        "life_tags",
        "appearance_relation_tags",
        "monetization",
    )
    @classmethod
    def dedupe_preserve_order(cls, value: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = (item or "").strip()
            if not normalized or normalized in seen:
                continue
            deduped.append(normalized)
            seen.add(normalized)
        return deduped


class MatchDecision(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    is_same_creator: bool
    match_confidence: MatchConfidence
    match_reason: str
    conflict_points: list[str] = Field(default_factory=list)
    next_action: NextAction
    score: int = 0


class RunSummary(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    stage: WorkflowStage
    run_id: str
    duration_minutes: float
    processed_candidates: int
    successful_records: int
    skipped_items: int
    blocked_items: int
    next_stage_ready: int
    output_path: str | None = None
    queue_path: str | None = None
