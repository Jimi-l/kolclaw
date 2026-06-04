from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from search_agent.enums import MatchConfidence, NextAction, RecordStatus


class XingtuEnrichmentRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    creator_name: str
    platform: Literal["douyin"] = "douyin"
    status: RecordStatus = RecordStatus.QUEUED_FOR_XINGTU

    xingtu_id: str | None = None
    xingtu_profile_url: str | None = None
    xingtu_creator_type: str | None = None
    match_confidence: MatchConfidence = MatchConfidence.LOW
    match_reason: str | None = None
    search_name_used: str

    price_20s: float | None = None
    price_20_60s: float | None = None
    price_60s_plus: float | None = None
    price_insert_video: float | None = None
    price_custom_video: float | None = None
    price_douyin_image_text: float | None = None
    other_service_prices: dict[str, float] | None = None

    estimated_play: str | int | None = None
    sponsored_median_play: str | int | None = None
    natural_cpm: float | None = None
    cpe: float | None = None
    sponsored_completion_rate: str | float | None = None

    monthly_fan_growth_rate: str | float | None = None
    monthly_connected_user_fan_ratio: str | float | None = None
    monthly_deep_user_fan_ratio: str | float | None = None

    recent_15_curve_screenshot_path: str | None = None
    cooperate_brands: list[str] | None = None
    field_missing_list: list[str] = Field(default_factory=list)
    enrichment_notes: str | None = None

    enrichment_status: RecordStatus
    next_action: NextAction

    @model_validator(mode="after")
    def validate_record(self) -> "XingtuEnrichmentRecord":
        completed_like = {RecordStatus.XINGTU_COMPLETED, RecordStatus.FIELD_PARTIAL}
        if self.enrichment_status in completed_like:
            if self.match_confidence == MatchConfidence.LOW:
                raise ValueError("completed-like enrichment records cannot keep low confidence")
            if not any((self.xingtu_id, self.xingtu_profile_url, self.xingtu_creator_type)):
                raise ValueError("completed-like enrichment records need at least one Xingtu identity anchor")
        if self.enrichment_status == RecordStatus.AMBIGUOUS_MATCH and self.next_action != NextAction.MANUAL_REVIEW:
            raise ValueError("ambiguous_match requires next_action=manual_review")
        if self.enrichment_status == RecordStatus.BLOCKED and self.next_action != NextAction.RETRY_LATER:
            raise ValueError("blocked enrichment records must use next_action=retry_later")
        return self
