from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from search_agent.enums import AnalysisStatus


class GeminiAnalysisPayload(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    video_content_summary: str
    content_taxonomy_path: list[str] = Field(default_factory=list)
    content_leaf_tags: list[str] = Field(default_factory=list)
    profession_tags: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    life_tags: list[str] = Field(default_factory=list)
    appearance_relation_tags: list[str] = Field(default_factory=list)
    monetization: list[str] = Field(default_factory=list)
    cooperate_type: str | None = None
    content_analysis_reasoning: str
    safety_or_uncertainty_note: str | None = None

    @model_validator(mode="after")
    def validate_lengths(self) -> "GeminiAnalysisPayload":
        if len(self.content_taxonomy_path) > 4:
            raise ValueError("content_taxonomy_path must contain at most 4 items")
        return self


class ContentAnalysisRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    source_stage: Literal["content-analysis"] = "content-analysis"
    platform: Literal["douyin"] = "douyin"
    creator_name: str | None = None
    video_url: str | None = None
    analysis_status: AnalysisStatus
    analysis_backend: str
    analysis_model: str | None = None
    keyframe_paths: list[str] = Field(default_factory=list)
    video_content_summary: str | None = None
    content_taxonomy_path: list[str] = Field(default_factory=list)
    content_leaf_tags: list[str] = Field(default_factory=list)
    profession_tags: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    life_tags: list[str] = Field(default_factory=list)
    appearance_relation_tags: list[str] = Field(default_factory=list)
    monetization: list[str] = Field(default_factory=list)
    cooperate_type: str | None = None
    content_analysis_reasoning: str | None = None
    analysis_error: str | None = None
