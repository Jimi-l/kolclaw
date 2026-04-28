from search_agent.enums import MatchConfidence, NextAction, RecordStatus, TrafficTrend
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.utils.dedup import build_duplicate_key, build_record_id
from search_agent.utils.matching import evaluate_xingtu_match


def make_discovery_record() -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=build_record_id("示例达人A"),
        status=RecordStatus.QUEUED_FOR_XINGTU,
        collection_date="2026/04/07",
        video_url="https://www.douyin.com/video/1",
        total_interaction_text="👍82.4万",
        creator_name="示例达人A",
        follower_count_raw="18.7万",
        follower_count_normalized=187000,
        traffic_trend=TrafficTrend.VOLATILE,
        content_taxonomy_path=["美妆个护", "护肤保养", "面部护肤"],
        content_leaf_tags=["面部护肤"],
        interest_tags=["穿搭"],
        monetization=[],
        duplicate_key=build_duplicate_key("douyin", "示例达人A"),
        next_action=NextAction.QUEUE_FOR_XINGTU,
    )


def test_match_confidence_high() -> None:
    decision = evaluate_xingtu_match(
        make_discovery_record(),
        candidate_name="示例达人A",
        candidate_follower_hint="19万粉丝",
        candidate_creator_type="美妆个护 面部护肤",
        candidate_content_hint="面部护肤 补水 防晒",
    )
    assert decision.match_confidence == MatchConfidence.HIGH
    assert decision.is_same_creator is True


def test_match_confidence_low_on_conflict() -> None:
    decision = evaluate_xingtu_match(
        make_discovery_record(),
        candidate_name="示例达人A",
        candidate_follower_hint="820万粉丝",
        candidate_creator_type="汽车",
        candidate_content_hint="试驾 新能源",
    )
    assert decision.match_confidence == MatchConfidence.LOW
    assert decision.next_action == NextAction.MANUAL_REVIEW
