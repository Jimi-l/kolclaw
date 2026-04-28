from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    brief_match: float = Field(default=0.0, ge=0.0, le=100.0)
    content_fit: float = Field(default=0.0, ge=0.0, le=100.0)
    audience_fit: float = Field(default=0.0, ge=0.0, le=100.0)
    commercial_efficiency: float = Field(default=0.0, ge=0.0, le=100.0)
    growth_signal: float = Field(default=0.0, ge=0.0, le=100.0)
    weighted_total: float = Field(default=0.0, ge=0.0, le=100.0)
    explanation: list[str] = Field(default_factory=list)
