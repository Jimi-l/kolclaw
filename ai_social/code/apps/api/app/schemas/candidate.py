from pydantic import BaseModel, Field

from app.schemas.scoring import ScoreBreakdown


class CandidateCreator(BaseModel):
    creator_id: str
    creator_name: str
    platform: str
    creator_types: list[str] = Field(default_factory=list)
    xingtu_link: str | None = None
    fans_count: int
    female_ratio: float
    core_female_ratio: float
    price: float
    rebate: float
    settlement_price_est: float
    median_commercial_play: int
    natural_cpm: float
    cpe: float
    commercial_completion_rate: float
    completion_cpm: float
    monthly_growth_rate: float
    broad_fan_ratio: float
    deep_fan_ratio: float
    recent_curve_summary: str
    recent_content_summary: str
    experience_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    city: str | None = None
    score_breakdown: ScoreBreakdown | None = None
    final_score: float = 0.0
    risk_notes: list[str] = Field(default_factory=list)
    recommendation_reason: str = ""
    recommendation_level: str = "Watch"
