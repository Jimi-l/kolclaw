from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.reference_docs import ExternalDocReference
from app.schemas.xingtu import XingtuCreatorDetail, XingtuFilterConfig


class RequirementConstraintBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creator_categories: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    content_themes: list[str] = Field(default_factory=list)
    audience_traits: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    min_fans_count: int | None = None
    budget_cap_per_creator: float | None = None
    notes: list[str] = Field(default_factory=list)


class ShortlistRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str | None = None
    product_name: str | None = None
    product_sku: str | None = None
    product_category: str | None = None
    platform: str = "douyin"
    city: str | None = None
    target_audience: list[str] = Field(default_factory=list)
    kpi_goals: list[str] = Field(default_factory=list)
    budget_total: float | None = None
    content_style_tags: list[str] = Field(default_factory=list)
    tone_tags: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    optional_notes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    hard_constraints: RequirementConstraintBucket = Field(default_factory=RequirementConstraintBucket)
    preferred_constraints: RequirementConstraintBucket = Field(default_factory=RequirementConstraintBucket)
    negotiable_constraints: RequirementConstraintBucket = Field(default_factory=RequirementConstraintBucket)


class ShortlistInputBase(BaseModel):
    raw_text: str | None = None
    structured_requirement: ShortlistRequirement | None = None

    @model_validator(mode="after")
    def validate_single_input(self) -> "ShortlistInputBase":
        has_raw = bool(self.raw_text and self.raw_text.strip())
        if has_raw == bool(self.structured_requirement):
            raise ValueError("Provide either raw_text or structured_requirement.")
        return self


class ShortlistParseRequest(ShortlistInputBase):
    pass


class ShortlistSearchPlan(BaseModel):
    platform: str
    filter_config: XingtuFilterConfig = Field(default_factory=XingtuFilterConfig)
    generated_keywords: list[str] = Field(default_factory=list)
    hard_filter_summary: list[str] = Field(default_factory=list)
    ranking_priorities: list[str] = Field(default_factory=list)
    search_notes: list[str] = Field(default_factory=list)
    unapplied_constraints: list[str] = Field(default_factory=list)
    collection_limit: int = Field(default=5, ge=1, le=20)
    shortlist_limit: int = Field(default=5, ge=1, le=20)


class ShortlistPlanRequest(ShortlistInputBase):
    collection_limit: int = Field(default=8, ge=1, le=20)
    shortlist_limit: int = Field(default=5, ge=1, le=20)


class ShortlistRunRequest(ShortlistPlanRequest):
    storage_state_path: str | None = None
    account_name: str | None = None
    base_url: str | None = None
    headless: bool = True


class ShortlistParseResponse(BaseModel):
    structured_requirement: ShortlistRequirement
    parser_notes: list[str] = Field(default_factory=list)


class ShortlistPlanResponse(BaseModel):
    structured_requirement: ShortlistRequirement
    parser_notes: list[str] = Field(default_factory=list)
    search_plan: ShortlistSearchPlan
    reference_docs: list[ExternalDocReference] = Field(default_factory=list)


class ShortlistScoreBreakdown(BaseModel):
    brief_match: float = Field(default=0.0, ge=0.0, le=100.0)
    audience_match: float = Field(default=0.0, ge=0.0, le=100.0)
    content_fit: float = Field(default=0.0, ge=0.0, le=100.0)
    quality_activity: float = Field(default=0.0, ge=0.0, le=100.0)
    commercial_signal: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    total_score: float = Field(default=0.0, ge=0.0, le=100.0)
    explanation: list[str] = Field(default_factory=list)


class ShortlistCandidate(BaseModel):
    creator: XingtuCreatorDetail
    score_breakdown: ShortlistScoreBreakdown
    recommendation_reason: str
    recommendation_level: str
    risk_flags: list[str] = Field(default_factory=list)


class ShortlistRunMetadata(BaseModel):
    storage_state_path: str
    account_name: str | None = None
    homepage_url: str | None = None
    creator_search_url: str | None = None
    rows_seen: int = 0
    creators_collected: int = 0
    creators_ranked: int = 0
    creators_filtered_out: int = 0
    filtered_out_reasons: dict[str, int] = Field(default_factory=dict)
    collection_errors: list[str] = Field(default_factory=list)


class ShortlistRunResponse(BaseModel):
    raw_brief: str | None = None
    structured_requirement: ShortlistRequirement
    parser_notes: list[str] = Field(default_factory=list)
    search_plan: ShortlistSearchPlan
    collected_creators: list[XingtuCreatorDetail] = Field(default_factory=list)
    shortlist: list[ShortlistCandidate] = Field(default_factory=list)
    reference_docs: list[ExternalDocReference] = Field(default_factory=list)
    metadata: ShortlistRunMetadata
    debug: dict[str, Any] = Field(default_factory=dict)
