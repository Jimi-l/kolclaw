from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScreenshotType(str, Enum):
    OVERVIEW_PRICING = "overview_pricing"
    VALUE_PERSONAL_VIDEO = "value_personal_video"
    LATEST15_PERSONAL_CHART = "latest15_personal_chart"
    LATEST15_STAR_CHART = "latest15_star_chart"
    UNKNOWN = "unknown"


REQUIRED_SCREENSHOT_TYPES: tuple[ScreenshotType, ...] = (
    ScreenshotType.OVERVIEW_PRICING,
    ScreenshotType.VALUE_PERSONAL_VIDEO,
    ScreenshotType.LATEST15_PERSONAL_CHART,
    ScreenshotType.LATEST15_STAR_CHART,
)


class ExtractedField(BaseModel):
    field_name: str
    raw_value: str | None = None
    normalized_value: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Literal["vlm", "manual", "fallback", "derived", "fixture"] = "vlm"
    screenshot_type: ScreenshotType = ScreenshotType.UNKNOWN
    evidence_text: str | None = None


class XingtuCpmInput(BaseModel):
    creator_name: str | None = None
    natural_plays: list[int] = Field(default_factory=list)
    sponsored_plays: list[int] = Field(default_factory=list)
    personal_chart_points: list["ChartPoint"] = Field(default_factory=list)
    star_chart_points: list["ChartPoint"] = Field(default_factory=list)
    post_count_30d: int | None = None
    post_count_30d_source: Literal["value_page", "chart_dates", "manual"] | None = None
    chart_date_count_30d_personal: int | None = None
    chart_date_count_30d_star: int | None = None
    chart_date_count_30d_total: int | None = None
    ad_mode_play: int | None = None
    ad_median_play: int | None = None
    ad_bucketed_mode_play: int | None = None
    price_20s: float | None = None
    price_20_60s: float | None = None
    price_60s_plus: float | None = None
    platform_expected_cpm: float | None = None
    platform_expected_play: int | None = None
    personal_chart_min_play: int | None = None
    personal_chart_max_play: int | None = None
    personal_chart_avg_play: int | None = None
    star_chart_min_play: int | None = None
    star_chart_max_play: int | None = None
    star_chart_avg_play: int | None = None
    sponsored_completion_rate: float | None = None
    monthly_fan_growth_rate: float | None = None
    monthly_connected_user_fan_ratio: float | None = None
    monthly_deep_user_fan_ratio: float | None = None
    creator_type: str | None = None
    cooperate_brands: list[str] = Field(default_factory=list)


class BucketedModeConfig(BaseModel):
    enabled: bool = True
    bucket_ratio: float = Field(default=0.25, gt=0.0)
    min_bucket_width: int = Field(default=10000, ge=1)
    prefer_lower_bucket_on_tie: bool = True


class TrafficClusterConfig(BaseModel):
    adjacent_ratio_threshold: float = Field(default=1.35, gt=1.0)
    min_cluster_size: int = Field(default=2, ge=1)
    primary_range_ratio: float = Field(default=0.2, ge=0.0)
    secondary_min_multiple: float = Field(default=1.6, gt=0.0)
    secondary_max_multiple: float = Field(default=4.5, gt=0.0)
    fallback_secondary_multiple: float = Field(default=2.5, gt=0.0)
    secondary_quantile_low: float = Field(default=0.55, ge=0.0, le=1.0)
    secondary_quantile_high: float = Field(default=0.8, ge=0.0, le=1.0)
    outlier_iqr_multiplier: float = Field(default=1.5, ge=0.0)
    outlier_max_to_median_ratio: float = Field(default=3.0, gt=1.0)


class TimeDecayConfig(BaseModel):
    days_90_weight: float = Field(default=1.0, ge=0.0)
    days_180_weight: float = Field(default=0.7, ge=0.0)
    days_365_weight: float = Field(default=0.4, ge=0.0)
    older_weight: float = Field(default=0.1, ge=0.0)


class TrendMetrics(BaseModel):
    trend_coefficient: float = 1.0
    trend_direction: str = "stable"
    first_half_median: int | None = None
    second_half_median: int | None = None


class ChartPoint(BaseModel):
    date: str | None = None
    play: int | None = None
    image_name: str | None = None


class CommercialAbilityMetrics(BaseModel):
    ability_score: float = 0.5
    ability_level: str = "unknown"
    coefficient: float = 1.0
    explanation: str = ""
    historical_commercial_position: str | None = None


class ConfidenceConfig(BaseModel):
    initial_score: float = 100.0
    missing_required_field_penalty: float = 10.0
    low_natural_count_penalty: float = 25.0
    no_secondary_pool_penalty: float = 12.0
    ad_stat_divergence_penalty: float = 10.0
    price_issue_penalty: float = 8.0
    low_post_count_penalty: float = 8.0
    very_low_post_count_penalty: float = 15.0
    review_threshold: float = 70.0


class WeightedPredictionConfig(BaseModel):
    commercial_ability_high_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    commercial_ability_good_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    commercial_ability_normal_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    commercial_ability_low_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    trend_min_coefficient: float = Field(default=0.7, gt=0.0)
    trend_max_coefficient: float = Field(default=1.3, gt=0.0)
    commercial_coefficient_min: float = Field(default=0.6, gt=0.0)
    commercial_coefficient_max: float = Field(default=1.2, gt=0.0)
    engagement_coefficient: float = Field(default=1.0, gt=0.0)


class XingtuCpmRuleConfig(BaseModel):
    min_valid_natural_plays: int = Field(default=8, ge=1)
    ad_repr_median_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    ad_stat_divergence_ratio: float = Field(default=2.5, gt=1.0)
    price_min: float = Field(default=1.0, ge=0.0)
    price_max: float = Field(default=10_000_000.0, gt=0.0)
    post_count_discount_factors: dict[int, float] = Field(
        default_factory=lambda: {0: 0.0, 1: 3.0, 2: 2.6, 3: 2.4, 4: 2.2, 5: 2.0, 6: 1.0}
    )
    bucketed_mode: BucketedModeConfig = Field(default_factory=BucketedModeConfig)
    clustering: TrafficClusterConfig = Field(default_factory=TrafficClusterConfig)
    time_decay: TimeDecayConfig = Field(default_factory=TimeDecayConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    weighted_prediction: WeightedPredictionConfig = Field(default_factory=WeightedPredictionConfig)


class PoolEstimate(BaseModel):
    center: int | None = None
    low: int | None = None
    high: int | None = None
    raw_center: int | None = None
    adjustment_factor: float = 1.0
    cluster_values: list[int] = Field(default_factory=list)
    explanation: str = ""
    source: str = "insufficient_data"
    confidence: float = 0.0
    sample_count: int = 0
    weighted_sample_count: float = 0.0
    is_estimated: bool = False
    outlier_count: int = 0
    age_weighted: bool = False


class CpmTierResult(BaseModel):
    price: float | None = None
    predicted_cpm: float | None = None
    natural_cpm: float | None = None
    reason: str | None = None
    commercial_cpm_play_basis_source: str | None = None
    natural_cpm_play_basis_source: str | None = None


class XingtuCpmAssessment(BaseModel):
    primary_pool: PoolEstimate
    secondary_pool: PoolEstimate | None = None
    commercial_primary_pool: PoolEstimate | None = None
    commercial_secondary_pool: PoolEstimate | None = None
    commercial_cpm_play_basis: int | None = None
    natural_cpm_play_basis: int | None = None
    commercial_pool_center_for_cpm: int | None = None
    natural_pool_center_for_cpm: int | None = None
    commercial_level: str
    ad_repr_play: int | None = None
    predicted_ad_play: int | None = None
    weighted_predicted_ad_play: int | None = None
    cpm_by_tier: dict[str, CpmTierResult] = Field(default_factory=dict)
    confidence_score: float
    review_flag: bool
    review_reasons: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    reference: dict[str, int | float | None] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)
    natural_trend_metrics: TrendMetrics | None = None
    commercial_trend_metrics: TrendMetrics | None = None
    overall_trend_metrics: TrendMetrics | None = None
    trend_metrics: TrendMetrics | None = None
    commercial_ability: CommercialAbilityMetrics | None = None
    base_predicted_play: int | None = None
    final_prediction_factors: dict[str, float] = Field(default_factory=dict)


class XingtuCpmEvaluateRequest(BaseModel):
    input: XingtuCpmInput
    config: XingtuCpmRuleConfig = Field(default_factory=XingtuCpmRuleConfig)


class ExtractionConflict(BaseModel):
    field_name: str
    left_value: Any = None
    right_value: Any = None
    chosen_source: str
    reason: str


class VlmExtractedPayload(BaseModel):
    detected_screenshot_types: list[ScreenshotType] = Field(default_factory=list)
    creator_name: str | None = None
    price_20s: float | None = None
    price_20_60s: float | None = None
    price_60s_plus: float | None = None
    post_count_30d: int | None = None
    platform_expected_cpm: float | None = None
    platform_expected_play: int | None = None
    personal_chart_min_play: int | None = None
    personal_chart_max_play: int | None = None
    personal_chart_avg_play: int | None = None
    star_chart_min_play: int | None = None
    star_chart_max_play: int | None = None
    star_chart_avg_play: int | None = None
    ad_mode_play: int | None = None
    ad_median_play: int | None = None
    monthly_fan_growth_rate: float | None = None
    natural_plays: list[int] = Field(default_factory=list)
    sponsored_plays: list[int] = Field(default_factory=list)
    personal_chart_points: list[ChartPoint] = Field(default_factory=list)
    star_chart_points: list[ChartPoint] = Field(default_factory=list)
    screenshots: list[dict[str, Any]] = Field(default_factory=list)
    chart_tabs_by_image: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VlmExtractionResult(BaseModel):
    payload: VlmExtractedPayload
    model: str | None = None
    warning: str | None = None
    raw_response: str | None = None


class XingtuCpmParseResult(BaseModel):
    extraction_engine_used: str | None = None
    vlm_model_used: str | None = None
    vlm_raw_response_preview: str | None = None
    field_sources: dict[str, str] = Field(default_factory=dict)
    conflicts: list[ExtractionConflict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_screenshot_types: list[ScreenshotType] = Field(default_factory=list)
    missing_required_screenshot_types: list[ScreenshotType] = Field(default_factory=list)
    extracted_fields_by_screenshot_type: dict[ScreenshotType, list[ExtractedField]] = Field(default_factory=dict)
    parsed_input: XingtuCpmInput
    parser_notes: list[str] = Field(default_factory=list)


class XingtuCpmAnalyzeResponse(BaseModel):
    parse_result: XingtuCpmParseResult
    assessment: XingtuCpmAssessment
