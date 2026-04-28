from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from browser_runtime import BrowserRuntime, BrowserRuntimeConfig
from feishu_client import FeishuClient
from llm_client import LLMClient
from models import CreatorRecord, VideoCandidate, WorkflowSummary
from storage import LocalStorage
from utils import (
    classify_traffic_trend,
    configure_logger,
    dedupe_keep_order,
    ensure_dir,
    env_flag,
    format_total_interactions,
    freshness_score_from_dates,
    load_prompt,
    now_iso,
    parse_cn_count,
)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


VIRAL_THRESHOLDS = {
    "like_count": 200_000,
    "share_count": 100_000,
    "favorite_count": 100_000,
    "comment_count": 10_000,
}


@dataclass
class DouyinWorkflowConfig:
    mock_mode: bool = True
    max_minutes: int = 20
    target_creators: int = 10
    db_path: str = "data/cache/creator_discovery.db"
    log_dir: str = "data/logs"
    screenshot_dir: str = "data/screenshots"
    douyin_url: str = "https://www.douyin.com"
    write_feishu: bool = False


class DouyinDiscoveryWorkflow:
    def __init__(self, config: DouyinWorkflowConfig) -> None:
        self.config = config
        ensure_dir(self.config.log_dir)
        ensure_dir(Path(self.config.db_path).parent)
        ensure_dir(self.config.screenshot_dir)

        self.logger = configure_logger("douyin_workflow", self.config.log_dir)
        self.storage = LocalStorage(db_path=self.config.db_path, log_dir=self.config.log_dir)
        self.browser = BrowserRuntime(
            BrowserRuntimeConfig(
                mock_mode=self.config.mock_mode,
                screenshot_dir=Path(self.config.screenshot_dir),
            )
        )
        self.llm = LLMClient(log_dir=self.config.log_dir)
        self.feishu = FeishuClient(log_dir=self.config.log_dir)
        self._mock_feed_index = 0

    def run(self) -> WorkflowSummary:
        summary = WorkflowSummary(workflow_name="douyin_discovery")
        started = time.time()
        checkpoint_key = "douyin_discovery:last_run"

        self.logger.info(
            "Start Douyin discovery workflow (mock_mode=%s, target=%s, max_minutes=%s)",
            self.config.mock_mode,
            self.config.target_creators,
            self.config.max_minutes,
        )

        try:
            self.login_and_prepare_feed()

            while not self._should_stop(summary=summary, started=started):
                feed_item = self.scan_recommended_feed()
                if not feed_item:
                    summary.skipped_count += 1
                    summary.notes.append("No feed item available in current cycle")
                    break

                summary.processed_count += 1

                filter_result = self.filter_feed_item(feed_item)
                if filter_result["decision"] == "skip":
                    summary.skipped_count += 1
                    self.logger.info("Skip feed item: %s", filter_result["reason"])
                    continue

                candidate = self.build_video_candidate(feed_item)
                creator_record = self.analyze_creator_profile(candidate=candidate, feed_item=feed_item)
                status, merged_record = self.storage.upsert_creator_record(creator_record)

                if self.config.write_feishu:
                    self.feishu.upsert_creator_record(merged_record)

                if status == "created":
                    summary.created_count += 1
                else:
                    summary.updated_count += 1

                summary.creator_names.append(merged_record.creator_name)
                self.storage.save_checkpoint(
                    checkpoint_key,
                    {
                        "last_creator_name": merged_record.creator_name,
                        "processed_count": summary.processed_count,
                        "created_count": summary.created_count,
                        "updated_count": summary.updated_count,
                    },
                )
                summary.checkpoints.append(checkpoint_key)

            summary.finish(status="completed")
        except Exception as exc:  # pragma: no cover
            summary.error_count += 1
            summary.notes.append(str(exc))
            summary.finish(status="failed")
            self.logger.exception("Douyin discovery workflow failed")
        finally:
            self.storage.save_workflow_summary(summary)

        self.logger.info("Douyin discovery workflow finished with status=%s", summary.status)
        return summary

    def login_and_prepare_feed(self) -> None:
        with self.browser.session("douyin") as session:
            session.goto(self.config.douyin_url)
            session.ensure_logged_in(expected_hint="推荐流已加载，右上角显示已登录头像")
            session.scroll_feed(direction="down")
            self.logger.info("Douyin feed ready")

    def scan_recommended_feed(self) -> Optional[dict[str, Any]]:
        if self.config.mock_mode:
            feed = self._mock_feed()
            if self._mock_feed_index >= len(feed):
                return None
            item = feed[self._mock_feed_index]
            self._mock_feed_index += 1
            self.logger.info("Loaded mock feed item: %s", item["creator_name"])
            return item

        self.logger.info("TODO: replace scan_recommended_feed with live browser extraction")
        return None

    def filter_feed_item(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        if feed_item.get("is_ad"):
            return {"decision": "skip", "reason": "ad"}
        if feed_item.get("is_live"):
            return {"decision": "skip", "reason": "live"}

        thresholds_hit = [
            field_name
            for field_name, threshold in VIRAL_THRESHOLDS.items()
            if int(feed_item.get(field_name, 0)) >= threshold
        ]
        if not thresholds_hit:
            return {"decision": "skip", "reason": "low_signal"}
        return {"decision": "candidate", "reason": ",".join(thresholds_hit)}

    def build_video_candidate(self, feed_item: dict[str, Any]) -> VideoCandidate:
        publish_date = feed_item.get("publish_date")
        capture_date = now_iso()[:10]
        candidate = VideoCandidate(
            capture_date=capture_date,
            video_url=feed_item["video_url"],
            publish_date=publish_date,
            publish_time_text=feed_item.get("publish_time_text", publish_date),
            freshness_score=freshness_score_from_dates(publish_date=publish_date, capture_date=capture_date),
            creator_name=feed_item["creator_name"],
            like_count=int(feed_item.get("like_count", 0)),
            comment_count=int(feed_item.get("comment_count", 0)),
            share_count=int(feed_item.get("share_count", 0)),
            favorite_count=int(feed_item.get("favorite_count", 0)),
            follower_count=parse_cn_count(feed_item.get("follower_count")),
            follower_count_text=str(feed_item.get("follower_count", "")),
            total_interaction_text=format_total_interactions(
                int(feed_item.get("like_count", 0)),
                int(feed_item.get("comment_count", 0)),
                int(feed_item.get("share_count", 0)),
                int(feed_item.get("favorite_count", 0)),
            ),
            ai_generated_flag=bool(feed_item.get("ai_generated_flag", False)),
            detection_reasons=[feed_item.get("detection_reason", "viral_threshold_met")],
            raw_signals=feed_item,
        )
        candidate.validate()
        return candidate

    def analyze_creator_profile(self, candidate: VideoCandidate, feed_item: dict[str, Any]) -> CreatorRecord:
        recent_video_like_counts = feed_item.get("recent_video_like_counts", [])
        traffic_trend = classify_traffic_trend(
            recommended_video_likes=int(feed_item.get("recommended_video_like_count", candidate.like_count)),
            recent_video_likes=recent_video_like_counts,
        )
        tag_bundle = self.generate_creator_tags(feed_item)

        record = CreatorRecord(
            creator_name=candidate.creator_name,
            video_candidate=candidate,
            profile_url=feed_item.get("profile_url"),
            follower_count=candidate.follower_count,
            total_likes=int(feed_item.get("total_likes", 0)),
            recommended_video_position=feed_item.get("recommended_video_position"),
            recommended_video_like_count=int(feed_item.get("recommended_video_like_count", candidate.like_count)),
            recent_video_like_counts=[int(value) for value in recent_video_like_counts[:3]],
            traffic_trend=traffic_trend,
            persona_tags=tag_bundle["persona_tags"],
            content_tags=tag_bundle["content_tags"],
            scene_tags=tag_bundle["scene_tags"],
            ad_fit=tag_bundle["ad_fit"],
            analysis_notes=tag_bundle["analysis_notes"],
            enrichment_status="pending",
        )
        record.validate()
        return record

    def generate_creator_tags(self, feed_item: dict[str, Any]) -> dict[str, Any]:
        system_prompt = load_prompt("creator_tagging.md")
        user_prompt = (
            f"达人名称: {feed_item['creator_name']}\n"
            f"简介: {feed_item.get('bio', '')}\n"
            f"内容摘要: {feed_item.get('content_summary', '')}\n"
        )
        llm_summary = self.llm.complete(system_prompt=system_prompt, user_prompt=user_prompt)

        persona_tags = dedupe_keep_order(feed_item.get("persona_tags", []), limit=2)
        content_tags = dedupe_keep_order(feed_item.get("content_tags", []), limit=2)
        scene_tags = dedupe_keep_order(feed_item.get("scene_tags", []))

        if not persona_tags:
            persona_tags = ["待细化达人"]
        if not content_tags:
            content_tags = ["待细化内容"]

        analysis_notes = dedupe_keep_order(
            [
                feed_item.get("analysis_note", ""),
                f"LLM summary: {llm_summary}",
            ]
        )
        return {
            "persona_tags": persona_tags,
            "content_tags": content_tags,
            "scene_tags": scene_tags,
            "ad_fit": feed_item.get("ad_fit", "两者皆可"),
            "analysis_notes": analysis_notes,
        }

    def _should_stop(self, summary: WorkflowSummary, started: float) -> bool:
        elapsed_minutes = (time.time() - started) / 60
        if elapsed_minutes >= self.config.max_minutes:
            summary.notes.append("Reached max runtime limit")
            return True
        if summary.created_count >= self.config.target_creators:
            summary.notes.append("Reached creator target")
            return True
        return False

    def _mock_feed(self) -> list[dict[str, Any]]:
        return [
            {
                "creator_name": "广告样例号",
                "video_url": "https://www.douyin.com/video/mock-ad-1",
                "publish_date": "2026-04-06",
                "follower_count": "5万",
                "like_count": 50_000,
                "comment_count": 800,
                "share_count": 400,
                "favorite_count": 600,
                "is_ad": True,
                "is_live": False,
                "content_summary": "广告样例",
            },
            {
                "creator_name": "白昼小熊",
                "video_url": "https://www.douyin.com/video/mock-creator-1",
                "publish_date": "2026-04-05",
                "follower_count": "125.6万",
                "like_count": 1_512_000,
                "comment_count": 23_000,
                "share_count": 110_000,
                "favorite_count": 180_000,
                "recommended_video_like_count": 1_512_000,
                "recent_video_like_counts": [1_537_000, 846_000, 603_000],
                "recommended_video_position": "中间",
                "profile_url": "https://www.douyin.com/user/mock-bzx",
                "total_likes": 8_200_000,
                "persona_tags": ["颜值博主", "时尚穿搭"],
                "content_tags": ["颜值展示", "卡点变装"],
                "scene_tags": ["工作室", "户外"],
                "ad_fit": "曝光植入型",
                "bio": "高频变装和视觉表达",
                "content_summary": "高颜值变装、卡点节奏、时尚表达",
                "analysis_note": "mock: 高互动变装达人",
                "is_ad": False,
                "is_live": False,
            },
            {
                "creator_name": "通勤阿琳",
                "video_url": "https://www.douyin.com/video/mock-creator-2",
                "publish_date": "2026-04-01",
                "follower_count": "48万",
                "like_count": 265_000,
                "comment_count": 11_000,
                "share_count": 18_000,
                "favorite_count": 54_000,
                "recommended_video_like_count": 265_000,
                "recent_video_like_counts": [120_000, 98_000, 76_000],
                "recommended_video_position": "置顶",
                "profile_url": "https://www.douyin.com/user/mock-alin",
                "total_likes": 2_950_000,
                "persona_tags": ["职场精英"],
                "content_tags": ["生活vlog", "好物种草"],
                "scene_tags": ["职场", "商场"],
                "ad_fit": "两者皆可",
                "bio": "通勤生活与职场分享",
                "content_summary": "白领日常、通勤穿搭、办公室好物",
                "analysis_note": "mock: 兼顾场景植入和种草",
                "is_ad": False,
                "is_live": False,
            },
        ]


def build_config(args: argparse.Namespace) -> DouyinWorkflowConfig:
    base_dir = Path(__file__).resolve().parents[1]
    return DouyinWorkflowConfig(
        mock_mode=args.mock,
        max_minutes=args.max_minutes,
        target_creators=args.target_creators,
        db_path=os.getenv("DISCOVERY_DB_PATH", str(base_dir / "data/cache/creator_discovery.db")),
        log_dir=os.getenv("DISCOVERY_LOG_DIR", str(base_dir / "data/logs")),
        screenshot_dir=os.getenv("DISCOVERY_SCREENSHOT_DIR", str(base_dir / "data/screenshots")),
        douyin_url=os.getenv("DOUYIN_HOME_URL", "https://www.douyin.com"),
        write_feishu=args.write_feishu,
    )


def main() -> None:
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Run the Douyin discovery workflow skeleton")
    parser.add_argument("--mock", action="store_true", default=env_flag("DISCOVERY_MOCK_MODE", True))
    parser.add_argument("--max-minutes", type=int, default=20)
    parser.add_argument("--target-creators", type=int, default=10)
    parser.add_argument("--write-feishu", action="store_true", default=False)
    args = parser.parse_args()

    workflow = DouyinDiscoveryWorkflow(build_config(args))
    summary = workflow.run()
    print(summary.to_dict())


if __name__ == "__main__":
    main()
