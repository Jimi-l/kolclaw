from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class BriefConstraints(BaseModel):
    min_fans_count: int | None = None
    min_female_ratio: float | None = None
    max_candidate_price: float | None = None
    required_creator_types: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CampaignBrief(BaseModel):
    campaign_id: str
    campaign_name: str
    platform: str
    budget_total: float
    creator_tier: str
    creator_types: list[str] = Field(default_factory=list)
    city: str
    event_date: date
    post_dates: list[date] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    constraints: BriefConstraints = Field(default_factory=BriefConstraints)
    keywords: list[str] = Field(default_factory=list)


class BriefStructureRequest(BaseModel):
    raw_text: str | None = None
    structured_draft: CampaignBrief | None = None

    @model_validator(mode="after")
    def validate_input(self) -> "BriefStructureRequest":
        if bool(self.raw_text and self.raw_text.strip()) == bool(self.structured_draft):
            raise ValueError("Provide either raw_text or structured_draft.")
        return self


class BriefStructureResponse(BaseModel):
    structured_brief: CampaignBrief
    parser_notes: list[str] = Field(default_factory=list)
