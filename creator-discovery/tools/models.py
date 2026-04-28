from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_record_id() -> str:
    return f"creator_{uuid4().hex[:12]}"


def _format_interaction_text(
    like_count: int,
    comment_count: int,
    share_count: int,
    favorite_count: int,
) -> str:
    return (
        f"👍{like_count} "
        f"💬{comment_count} "
        f"↗️{share_count} "
        f"⭐{favorite_count}"
    )


class ModelValidationError(ValueError):
    """Raised when a model instance is invalid for the current V0 contract."""


@dataclass
class VideoCandidate:
    capture_date: str
    video_url: str
    creator_name: str
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    favorite_count: int = 0
    publish_date: Optional[str] = None
    publish_time_text: Optional[str] = None
    freshness_score: Optional[int] = None
    follower_count: Optional[int] = None
    follower_count_text: Optional[str] = None
    total_interaction_text: Optional[str] = None
    ai_generated_flag: bool = False
    detected_as_potential: bool = True
    detection_reasons: list[str] = field(default_factory=list)
    raw_signals: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.capture_date:
            raise ModelValidationError("VideoCandidate.capture_date is required")
        if not self.video_url.startswith("http"):
            raise ModelValidationError("VideoCandidate.video_url must be an absolute URL")
        if not self.creator_name.strip():
            raise ModelValidationError("VideoCandidate.creator_name is required")

        numeric_fields = (
            ("like_count", self.like_count),
            ("comment_count", self.comment_count),
            ("share_count", self.share_count),
            ("favorite_count", self.favorite_count),
        )
        for field_name, value in numeric_fields:
            if value < 0:
                raise ModelValidationError(f"VideoCandidate.{field_name} must be >= 0")

        if self.follower_count is not None and self.follower_count < 0:
            raise ModelValidationError("VideoCandidate.follower_count must be >= 0")

        if self.freshness_score is not None and self.freshness_score not in {50, 60, 70, 80, 90, 100}:
            raise ModelValidationError("VideoCandidate.freshness_score must follow the V0 score buckets")

        if not self.total_interaction_text:
            self.total_interaction_text = _format_interaction_text(
                self.like_count,
                self.comment_count,
                self.share_count,
                self.favorite_count,
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoCandidate":
        instance = cls(**payload)
        instance.validate()
        return instance


@dataclass
class XingtuRecord:
    xingtu_id: Optional[str] = None
    creator_types: list[str] = field(default_factory=list)
    profile_url: Optional[str] = None
    price_20s: Optional[int] = None
    price_20_to_60s: Optional[int] = None
    price_60s_plus: Optional[int] = None
    estimated_play_volume: Optional[str] = None
    sponsored_play_median: Optional[str] = None
    organic_cpm: Optional[str] = None
    cpe: Optional[str] = None
    completion_rate: Optional[str] = None
    play_curve_screenshot: Optional[str] = None
    monthly_follower_growth_rate: Optional[str] = None
    connected_user_fan_ratio: Optional[str] = None
    deep_user_fan_ratio: Optional[str] = None
    cooperative_clients: list[str] = field(default_factory=list)
    match_status: str = "pending"
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        allowed_statuses = {"pending", "complete", "partial", "not_found", "not_registered"}
        if self.match_status not in allowed_statuses:
            raise ModelValidationError(
                f"XingtuRecord.match_status must be one of {sorted(allowed_statuses)}"
            )

        if self.profile_url and not self.profile_url.startswith("http"):
            raise ModelValidationError("XingtuRecord.profile_url must be an absolute URL when present")

        for field_name in ("price_20s", "price_20_to_60s", "price_60s_plus"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ModelValidationError(f"XingtuRecord.{field_name} must be >= 0")

    def is_complete(self) -> bool:
        return self.match_status == "complete" and bool(self.xingtu_id)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "XingtuRecord":
        instance = cls(**payload)
        instance.validate()
        return instance


@dataclass
class CreatorRecord:
    creator_name: str
    video_candidate: VideoCandidate
    record_id: str = field(default_factory=_new_record_id)
    platform: str = "douyin"
    profile_url: Optional[str] = None
    follower_count: Optional[int] = None
    total_likes: Optional[int] = None
    recommended_video_position: Optional[str] = None
    recommended_video_like_count: Optional[int] = None
    recent_video_like_counts: list[int] = field(default_factory=list)
    recent_video_average_like_count: Optional[float] = None
    traffic_trend: Optional[str] = None
    persona_tags: list[str] = field(default_factory=list)
    content_tags: list[str] = field(default_factory=list)
    scene_tags: list[str] = field(default_factory=list)
    ad_fit: Optional[str] = None
    analysis_notes: list[str] = field(default_factory=list)
    enrichment_status: str = "pending"
    xingtu_record: Optional[XingtuRecord] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def validate(self) -> None:
        if not self.creator_name.strip():
            raise ModelValidationError("CreatorRecord.creator_name is required")
        if self.platform != "douyin":
            raise ModelValidationError("CreatorRecord.platform currently only supports 'douyin' in V0")

        self.video_candidate.validate()

        if self.follower_count is not None and self.follower_count < 0:
            raise ModelValidationError("CreatorRecord.follower_count must be >= 0")
        if self.total_likes is not None and self.total_likes < 0:
            raise ModelValidationError("CreatorRecord.total_likes must be >= 0")
        if self.recommended_video_like_count is not None and self.recommended_video_like_count < 0:
            raise ModelValidationError("CreatorRecord.recommended_video_like_count must be >= 0")
        if any(value < 0 for value in self.recent_video_like_counts):
            raise ModelValidationError("CreatorRecord.recent_video_like_counts values must be >= 0")

        allowed_positions = {None, "置顶", "中间"}
        if self.recommended_video_position not in allowed_positions:
            raise ModelValidationError("CreatorRecord.recommended_video_position must be '置顶' or '中间'")

        allowed_trends = {None, "昙花一现", "流量波动", "持续爆款", "数据不足"}
        if self.traffic_trend not in allowed_trends:
            raise ModelValidationError("CreatorRecord.traffic_trend is outside the V0 contract")

        allowed_ad_fit = {None, "曝光植入型", "产品种草型", "两者皆可"}
        if self.ad_fit not in allowed_ad_fit:
            raise ModelValidationError("CreatorRecord.ad_fit is outside the V0 contract")

        allowed_enrichment = {"pending", "complete", "partial", "not_found", "not_registered"}
        if self.enrichment_status not in allowed_enrichment:
            raise ModelValidationError("CreatorRecord.enrichment_status is outside the V0 contract")

        if len(self.persona_tags) > 2:
            raise ModelValidationError("CreatorRecord.persona_tags supports at most 2 tags in V0")
        if len(self.content_tags) > 2:
            raise ModelValidationError("CreatorRecord.content_tags supports at most 2 tags in V0")

        if self.recent_video_like_counts and self.recent_video_average_like_count is None:
            self.recent_video_average_like_count = round(
                sum(self.recent_video_like_counts) / len(self.recent_video_like_counts),
                2,
            )

        if self.xingtu_record:
            self.xingtu_record.validate()
            if self.xingtu_record.match_status != "pending":
                self.enrichment_status = self.xingtu_record.match_status

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CreatorRecord":
        candidate = VideoCandidate.from_dict(payload["video_candidate"])
        xingtu_payload = payload.get("xingtu_record")
        xingtu_record = XingtuRecord.from_dict(xingtu_payload) if xingtu_payload else None

        instance = cls(
            creator_name=payload["creator_name"],
            video_candidate=candidate,
            record_id=payload.get("record_id", _new_record_id()),
            platform=payload.get("platform", "douyin"),
            profile_url=payload.get("profile_url"),
            follower_count=payload.get("follower_count"),
            total_likes=payload.get("total_likes"),
            recommended_video_position=payload.get("recommended_video_position"),
            recommended_video_like_count=payload.get("recommended_video_like_count"),
            recent_video_like_counts=payload.get("recent_video_like_counts", []),
            recent_video_average_like_count=payload.get("recent_video_average_like_count"),
            traffic_trend=payload.get("traffic_trend"),
            persona_tags=payload.get("persona_tags", []),
            content_tags=payload.get("content_tags", []),
            scene_tags=payload.get("scene_tags", []),
            ad_fit=payload.get("ad_fit"),
            analysis_notes=payload.get("analysis_notes", []),
            enrichment_status=payload.get("enrichment_status", "pending"),
            xingtu_record=xingtu_record,
            created_at=payload.get("created_at", _now_iso()),
            updated_at=payload.get("updated_at", _now_iso()),
        )
        instance.validate()
        return instance


@dataclass
class WorkflowSummary:
    workflow_name: str
    status: str = "running"
    started_at: str = field(default_factory=_now_iso)
    finished_at: Optional[str] = None
    duration_seconds: int = 0
    processed_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    creator_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    checkpoints: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.workflow_name.strip():
            raise ModelValidationError("WorkflowSummary.workflow_name is required")

        allowed_statuses = {"running", "completed", "failed", "partial"}
        if self.status not in allowed_statuses:
            raise ModelValidationError("WorkflowSummary.status is outside the V0 contract")

        for field_name in (
            "duration_seconds",
            "processed_count",
            "created_count",
            "updated_count",
            "skipped_count",
            "error_count",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ModelValidationError(f"WorkflowSummary.{field_name} must be >= 0")

    def finish(self, status: str = "completed") -> None:
        self.finished_at = _now_iso()
        self.status = status
        started = datetime.fromisoformat(self.started_at)
        finished = datetime.fromisoformat(self.finished_at)
        self.duration_seconds = max(0, int((finished - started).total_seconds()))
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorkflowSummary":
        instance = cls(**payload)
        instance.validate()
        return instance
