from search_agent.enums import NextAction, RecordStatus, TrafficTrend
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.utils.dedup import build_duplicate_key, build_record_id, decide_duplicate


def make_record(name: str, followers: int, content_leaf_tags: list[str]) -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=build_record_id(name),
        status=RecordStatus.QUEUED_FOR_XINGTU,
        collection_date="2026/04/07",
        video_url="https://www.douyin.com/video/1",
        total_interaction_text="👍20万",
        creator_name=name,
        follower_count_raw="12.5万",
        follower_count_normalized=followers,
        traffic_trend=TrafficTrend.SUSTAINED,
        content_taxonomy_path=["文化娱乐", "知识教育", "科普人文"],
        content_leaf_tags=content_leaf_tags,
        duplicate_key=build_duplicate_key("douyin", name),
        next_action=NextAction.QUEUE_FOR_XINGTU,
    )


def test_build_duplicate_key() -> None:
    assert build_duplicate_key("douyin", "示例 达人A") == "douyin::示例达人a"


def test_decide_duplicate_exact_match() -> None:
    existing = make_record("示例达人A", 125000, ["历史"])
    candidate = make_record("示例达人A", 130000, ["历史"])
    decision = decide_duplicate(candidate, [existing])
    assert decision.is_duplicate is True
    assert decision.requires_manual_review is False


def test_decide_duplicate_manual_review_on_content_conflict() -> None:
    existing = make_record("示例达人A", 125000, ["历史"])
    candidate = make_record("示例达人A", 130000, ["游戏解说"])
    decision = decide_duplicate(candidate, [existing])
    assert decision.is_duplicate is False
    assert decision.requires_manual_review is True
