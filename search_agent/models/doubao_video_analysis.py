from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DoubaoVideoAnalysisRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    workflow_run_id: str | None = None
    source_stage: Literal["douyin-doubao-video-analysis"] = "douyin-doubao-video-analysis"
    platform: Literal["douyin"] = "douyin"
    video_url: str
    creator_name: str | None = None
    file_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    analysis_model: str | None = None
    response_id: str | None = None
    is_viral: bool | None = None
    viral_rule_hit: str | None = None
    viral_rule_reasoning: str | None = None
    theme: str | None = None
    protagonist: str | None = None
    scene: str | None = None
    core_action: str | None = None
    story_traits: list[str] = Field(default_factory=list)
    visual_hooks: list[str] = Field(default_factory=list)
    replicability: str | None = None
    replicability_reasoning: str | None = None
    tags: list[str] = Field(default_factory=list)
    retention_reasons: list[str] = Field(default_factory=list)
    interaction_reasons: list[str] = Field(default_factory=list)
    opening_hook_analysis: str | None = None
    audience_emotion: dict = Field(default_factory=dict)
    core_audience: dict = Field(default_factory=dict)
    series_continuation_interest: str | None = None
    analysis_reasoning: str | None = None
    raw_response_text: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    updated_at: str
