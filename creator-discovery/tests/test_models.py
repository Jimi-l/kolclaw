from __future__ import annotations

import sys
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from models import CreatorRecord, ModelValidationError, VideoCandidate, WorkflowSummary, XingtuRecord  # noqa: E402


def build_video_candidate() -> VideoCandidate:
    return VideoCandidate(
        capture_date="2026-04-07",
        video_url="https://www.douyin.com/video/123",
        creator_name="测试达人",
        like_count=250_000,
        comment_count=12_000,
        share_count=5_000,
        favorite_count=10_000,
        publish_date="2026-04-05",
    )


def test_video_candidate_autofills_total_interactions() -> None:
    candidate = build_video_candidate()
    candidate.validate()
    assert candidate.total_interaction_text == "👍250000 💬12000 ↗️5000 ⭐10000"


def test_creator_record_rejects_too_many_persona_tags() -> None:
    candidate = build_video_candidate()
    with pytest.raises(ModelValidationError):
        CreatorRecord(
            creator_name="测试达人",
            video_candidate=candidate,
            persona_tags=["A", "B", "C"],
        ).validate()


def test_xingtu_record_complete_status_detection() -> None:
    xingtu_record = XingtuRecord(
        xingtu_id="mock_abc",
        profile_url="https://www.xingtu.cn/mock/abc",
        match_status="complete",
    )
    assert xingtu_record.is_complete() is True


def test_workflow_summary_finish_populates_status_and_duration() -> None:
    summary = WorkflowSummary(workflow_name="douyin_discovery")
    summary.finish(status="completed")
    assert summary.status == "completed"
    assert summary.finished_at is not None
    assert summary.duration_seconds >= 0
