from __future__ import annotations

from enum import Enum


class WorkflowStage(str, Enum):
    ROUTING = "routing"
    CREATOR_DISCOVERY = "creator-discovery"
    XINGTU_ENRICHMENT = "xingtu-enrichment"
    CONTENT_ANALYSIS = "content-analysis"
    VIDEO_URL_ANALYSIS = "video-url-analysis"
    DOUYIN_MP4_LINKS = "douyin-mp4-links"
    DOUYIN_MP4_FILES = "douyin-mp4-files"
    DOUYIN_DOUBAO_VIDEO_ANALYSIS = "douyin-doubao-video-analysis"
    DOUYIN_VIDEO_PIPELINE = "douyin-video-pipeline"
    DOUYIN_LIVE_WORKFLOW = "douyin-live-workflow"


class RecordStatus(str, Enum):
    NEW_TASK = "new_task"
    DISCOVERING = "discovering"
    DISCOVERED = "discovered"
    QUEUED_FOR_XINGTU = "queued_for_xingtu"
    ENRICHING = "enriching"
    XINGTU_COMPLETED = "xingtu_completed"
    XINGTU_NOT_FOUND = "xingtu_not_found"
    XINGTU_UNREGISTERED = "xingtu_unregistered"
    AMBIGUOUS_MATCH = "ambiguous_match"
    FIELD_PARTIAL = "field_partial"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class NextAction(str, Enum):
    QUEUE_FOR_XINGTU = "queue_for_xingtu"
    SKIP = "skip"
    MANUAL_REVIEW = "manual_review"
    DONE = "done"
    RETRY_LATER = "retry_later"
    CONTINUE = "continue"
    CONTINUE_WITH_CAUTION = "continue_with_caution"


class TrafficTrend(str, Enum):
    FLASH = "昙花一现"
    VOLATILE = "流量波动"
    SUSTAINED = "持续爆款"


class AdFit(str, Enum):
    EXPOSURE = "曝光植入型"
    PRODUCT = "产品种草型"
    BOTH = "两者皆可"


class MatchConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BlockReason(str, Enum):
    LOGIN_REQUIRED = "login_required"
    QR_LOGIN_REQUIRED = "qr_login_required"
    SMS_LOGIN_REQUIRED = "sms_login_required"
    CAPTCHA_REQUIRED = "captcha_required"
    CAPTCHA_BLOCKED = "captcha_blocked"
    SESSION_EXPIRED = "session_expired"
    PERMISSION_DENIED = "permission_denied"
    EXTERNAL_APP_INTERRUPTION = "external_app_interruption"
    XINGTU_ACCESS_RESTRICTED = "xingtu_access_restricted"
    PAGE_STRUCTURE_UNCERTAINTY = "page_structure_uncertainty"
    PAGE_UNREACHABLE = "page_unreachable"


class HotnessAgeScore(str, Enum):
    SCORE_100 = "100%"
    SCORE_90 = "90%"
    SCORE_80 = "80%"
    SCORE_70 = "70%"
    SCORE_60 = "60%"
    SCORE_50 = "50%"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FALLBACK = "fallback"
    FAILED = "failed"
