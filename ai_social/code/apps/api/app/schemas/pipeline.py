from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.brief import CampaignBrief
from app.schemas.candidate import CandidateCreator
from app.schemas.strategy_template import StrategyTemplate


class RetrievalPlan(BaseModel):
    selected_filters: dict[str, Any] = Field(default_factory=dict)
    generated_keywords: list[str] = Field(default_factory=list)
    hard_filter_summary: list[str] = Field(default_factory=list)
    ranking_priorities: list[str] = Field(default_factory=list)


class RetrievalPlanRequest(BaseModel):
    brief: CampaignBrief
    template_id: str | None = None
    template: StrategyTemplate | None = None

    @model_validator(mode="after")
    def validate_template_source(self) -> "RetrievalPlanRequest":
        if not self.template_id and not self.template:
            raise ValueError("Provide template_id or template.")
        return self


class CandidateRunRequest(BaseModel):
    brief: CampaignBrief
    template_id: str | None = None
    template: StrategyTemplate | None = None
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_template_source(self) -> "CandidateRunRequest":
        if not self.template_id and not self.template:
            raise ValueError("Provide template_id or template.")
        return self


class PipelineMetadata(BaseModel):
    template_id: str
    total_candidates_loaded: int
    candidates_after_filters: int
    filtered_out: int
    filter_reasons: dict[str, int] = Field(default_factory=dict)


class CandidatesRunResponse(BaseModel):
    brief: CampaignBrief
    template: StrategyTemplate
    retrieval_plan: RetrievalPlan
    candidates: list[CandidateCreator] = Field(default_factory=list)
    metadata: PipelineMetadata
