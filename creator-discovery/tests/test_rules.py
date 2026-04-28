from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from utils import (  # noqa: E402
    classify_traffic_trend,
    days_to_freshness_score,
    dedupe_keep_order,
    freshness_score_from_dates,
    parse_cn_count,
)


def test_parse_cn_count_handles_wan_and_yi() -> None:
    assert parse_cn_count("12.5万") == 125_000
    assert parse_cn_count("1.2亿") == 120_000_000
    assert parse_cn_count("3456") == 3456


def test_freshness_score_rules_match_business_buckets() -> None:
    assert days_to_freshness_score(2) == 100
    assert days_to_freshness_score(4) == 90
    assert days_to_freshness_score(9) == 80
    assert days_to_freshness_score(14) == 70
    assert days_to_freshness_score(20) == 60
    assert days_to_freshness_score(40) == 50
    assert freshness_score_from_dates("2026-04-05", "2026-04-07") == 100


def test_classify_traffic_trend_matches_spec() -> None:
    assert classify_traffic_trend(1_500_000, [100_000, 80_000, 50_000]) == "昙花一现"
    assert classify_traffic_trend(200_000, [70_000, 80_000, 60_000]) == "流量波动"
    assert classify_traffic_trend(300_000, [200_000, 190_000, 220_000]) == "持续爆款"


def test_dedupe_keep_order_preserves_order_and_limit() -> None:
    assert dedupe_keep_order(["A", "B", "A", "C"], limit=2) == ["A", "B"]
