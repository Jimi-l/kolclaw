from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class HardFilters(BaseModel):
    platform_match: bool = True
    min_fans_count: int | None = None
    min_female_ratio: float | None = None
    max_candidate_price: float | None = None
    max_price_share_of_budget: float | None = 0.35
    require_creator_type_overlap: bool = True


class SoftPreferences(BaseModel):
    preferred_cities: list[str] = Field(default_factory=list)
    preferred_experience_tags: list[str] = Field(default_factory=list)
    preferred_content_tags: list[str] = Field(default_factory=list)
    preferred_style_tags: list[str] = Field(default_factory=list)
    growth_floor: float | None = None


class ScoreWeights(BaseModel):
    brief_match: float = 0.30
    content_fit: float = 0.20
    commercial_efficiency: float = 0.20
    audience_fit: float = 0.15
    growth_signal: float = 0.15

    @model_validator(mode="after")
    def validate_weights(self) -> "ScoreWeights":
        total = (
            self.brief_match
            + self.content_fit
            + self.commercial_efficiency
            + self.audience_fit
            + self.growth_signal
        )
        if total <= 0:
            raise ValueError("At least one score weight must be greater than zero.")
        return self


class StrategyTemplate(BaseModel):
    template_id: str
    template_name: str
    description: str
    hard_filters: HardFilters
    soft_preferences: SoftPreferences = Field(default_factory=SoftPreferences)
    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    platform_mapping: dict[str, list[str]] = Field(default_factory=dict)
    manual_review_points: list[str] = Field(default_factory=list)
