from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.xingtu import (  # noqa: E402
    XingtuCreatorDetail,
    XingtuFilterConfig,
    XingtuLiveRunConfig,
)
from app.services.xingtu_workflow import _extract_core_metric_snapshot, validate_creator_detail  # noqa: E402
from app.services.xingtu_workflow import _extract_creator_id  # noqa: E402


class XingtuLiveFlowUnitTests(unittest.TestCase):
    def test_extract_core_metric_snapshot_from_recording_like_text(self) -> None:
        page_text = (
            "所选数据范围内视频播放量中位数（仅统计公开可见视频）播放量中位数6,344优于73.81%同类型达人 "
            "预期CPM8,480 "
            "所选数据范围内视频平均完播率（仅统计公开可见视频）完播率14.7%优于89.04%同类型达人 "
            "所选数据范围内视频平均互动率（仅统计公开可见视频）互动率2 "
            "月连接用户数77.4w 月深度用户数39.6w 粉丝数144.7w 月涨粉率6.31%"
        )

        metrics = _extract_core_metric_snapshot(page_text)

        self.assertEqual(metrics["avg_video_play_median"], 6344)
        self.assertAlmostEqual(metrics["avg_video_play_median_percentile"] or 0, 0.7381, places=4)
        self.assertEqual(metrics["expected_cpm"], 8480)
        self.assertAlmostEqual(metrics["average_completion_rate"] or 0, 0.147, places=4)
        self.assertAlmostEqual(metrics["average_completion_rate_percentile"] or 0, 0.8904, places=4)
        self.assertAlmostEqual(metrics["average_interaction_rate"] or 0, 0.02, places=4)
        self.assertEqual(metrics["monthly_connected_users"], 774000)
        self.assertEqual(metrics["monthly_deep_users"], 396000)
        self.assertAlmostEqual(metrics["monthly_growth_rate"] or 0, 0.0631, places=4)

    def test_validate_creator_detail_reports_missing_required_fields(self) -> None:
        detail = XingtuCreatorDetail(creator_name="测试达人")

        missing = validate_creator_detail(detail)

        self.assertEqual(missing, ["fans_count", "avg_video_play_median"])

    def test_live_run_config_accepts_minimal_filter_config(self) -> None:
        config = XingtuLiveRunConfig(
            storage_state_path=Path("/tmp/xingtu.json"),
            filter_config=XingtuFilterConfig(named_filters={"美妆": ["美妆测评种草"]}),
        )

        self.assertEqual(config.filter_config.named_filters["美妆"], ["美妆测评种草"])
        self.assertEqual(config.target_row_index, 0)
        self.assertEqual(config.row_limit, 5)

    def test_extract_creator_id_from_live_detail_url(self) -> None:
        creator_id = _extract_creator_id(
            "https://www.xingtu.cn/ad/creator/author-homepage/douyin-video/"
            "6870168961489567752?market_track_id=abc&search_session_id=123"
        )

        self.assertEqual(creator_id, "6870168961489567752")


if __name__ == "__main__":
    unittest.main()
