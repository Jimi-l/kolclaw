from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from search_agent.enums import AnalysisStatus


class ViralRuleSnapshot(BaseModel):
    share_count: int | None = None
    follower_count: int | None = None
    is_viral: bool
    rule_hit: str
    rule_reasoning: str


class AudienceProfile(BaseModel):
    age_bands: list[str] = Field(default_factory=list)
    gender_skew: str | None = None
    income_level: str | None = None
    city_tier_preference: list[str] = Field(default_factory=list)
    region_preference: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class EmotionArc(BaseModel):
    opening: str
    middle: str
    ending: str


class VideoUrlAnalysisPayload(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    video_access_status: Literal["accessible", "metadata_only", "uncertain"]
    theme: str
    protagonist: str
    scene: str
    core_action: str
    action_highlights: list[str] = Field(default_factory=list)
    encountered_people: list[str] = Field(default_factory=list)
    people_story_traits: list[str] = Field(default_factory=list)
    visual_highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    retention_reasons: list[str] = Field(default_factory=list)
    interaction_reasons: list[str] = Field(default_factory=list)
    opening_hook_analysis: str
    audience_emotion: EmotionArc
    core_audience: AudienceProfile
    replicability: Literal["高", "中", "低"]
    replicability_reasoning: str
    series_continuation_interest: str
    analysis_reasoning: str


class VideoUrlAnalysisRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    source_stage: Literal["video-url-analysis"] = "video-url-analysis"
    platform: Literal["douyin"] = "douyin"
    creator_name: str | None = None
    collection_date: str | None = None
    video_url: str
    analysis_status: AnalysisStatus
    analysis_backend: str
    analysis_model: str | None = None
    share_count_raw: str | None = None
    follower_count_raw: str | None = None
    share_count_normalized: int | None = None
    follower_count_normalized: int | None = None
    is_viral: bool | None = None
    viral_rule_hit: str | None = None
    viral_rule_reasoning: str | None = None
    video_access_status: str | None = None
    theme: str | None = None
    protagonist: str | None = None
    scene: str | None = None
    core_action: str | None = None
    action_highlights: list[str] = Field(default_factory=list)
    encountered_people: list[str] = Field(default_factory=list)
    people_story_traits: list[str] = Field(default_factory=list)
    visual_highlights: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    retention_reasons: list[str] = Field(default_factory=list)
    interaction_reasons: list[str] = Field(default_factory=list)
    opening_hook_analysis: str | None = None
    audience_emotion: EmotionArc | None = None
    core_audience: AudienceProfile | None = None
    replicability: str | None = None
    replicability_reasoning: str | None = None
    series_continuation_interest: str | None = None
    analysis_reasoning: str | None = None
    analysis_error: str | None = None
