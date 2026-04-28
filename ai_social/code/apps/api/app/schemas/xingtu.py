from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class XingtuFilterConfig(BaseModel):
    """Normalized filter payload for Xingtu creator search."""

    keyword: str | None = None
    named_filters: dict[str, list[str]] = Field(default_factory=dict)
    creator_types: list[str] = Field(default_factory=list)
    content_categories: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    fans_min: int | None = None
    fans_max: int | None = None
    female_ratio_min: float | None = None
    female_ratio_max: float | None = None
    sort_by: str | None = None
    extra_tags: list[str] = Field(default_factory=list)


class XingtuCreatorRow(BaseModel):
    """Normalized search-row payload before opening creator detail."""

    row_index: int
    creator_name: str | None = None
    creator_id: str | None = None
    xingtu_link: str | None = None
    creator_types: list[str] = Field(default_factory=list)
    city: str | None = None
    fans_count: int | None = None
    female_ratio: float | None = None
    quoted_price: float | None = None
    median_commercial_play: int | None = None
    natural_cpm: float | None = None
    raw_columns: list[str] = Field(default_factory=list)
    raw_text: str | None = None


class XingtuCreatorDetail(BaseModel):
    """Normalized detail-page payload shaped for later mapping into CandidateCreator."""

    creator_name: str | None = None
    creator_id: str | None = None
    xingtu_link: str | None = None
    platform: str = "douyin"
    creator_types: list[str] = Field(default_factory=list)
    city: str | None = None
    fans_count: int | None = None
    female_ratio: float | None = None
    core_female_ratio: float | None = None
    price: float | None = None
    rebate: float | None = None
    settlement_price_est: float | None = None
    avg_video_play_median: int | None = None
    avg_video_play_median_percentile: float | None = None
    expected_cpm: float | None = None
    average_completion_rate: float | None = None
    average_completion_rate_percentile: float | None = None
    average_interaction_rate: float | None = None
    average_interaction_rate_percentile: float | None = None
    monthly_connected_users: int | None = None
    monthly_deep_users: int | None = None
    median_commercial_play: int | None = None
    natural_cpm: float | None = None
    cpe: float | None = None
    commercial_completion_rate: float | None = None
    completion_cpm: float | None = None
    monthly_growth_rate: float | None = None
    broad_fan_ratio: float | None = None
    deep_fan_ratio: float | None = None
    recent_curve_summary: str | None = None
    recent_content_summary: str | None = None
    experience_tags: list[str] = Field(default_factory=list)
    raw_metrics: dict[str, str] = Field(default_factory=dict)
    raw_sections: dict[str, str] = Field(default_factory=dict)


class XingtuLiveRunConfig(BaseModel):
    """Config for the authenticated live Xingtu runner."""

    storage_state_path: Path
    account_name: str | None = None
    base_url: str | None = None
    headless: bool = True
    row_limit: int = 5
    target_row_index: int = 0
    filter_config: XingtuFilterConfig = Field(default_factory=XingtuFilterConfig)


class XingtuLiveRunResult(BaseModel):
    """Structured result from a single live Xingtu creator-detail flow."""

    storage_state_path: str
    homepage_url: str
    creator_search_url: str
    rows_collected: int
    selected_row: XingtuCreatorRow | None = None
    detail: XingtuCreatorDetail | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
