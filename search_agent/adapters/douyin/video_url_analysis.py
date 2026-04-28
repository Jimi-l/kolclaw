from __future__ import annotations

import logging
import time

from search_agent.artifacts import ArtifactManager
from search_agent.config import RuntimePaths, VideoUrlAnalysisRunConfig
from search_agent.enums import AnalysisStatus, WorkflowStage
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.video_url_analysis import VideoUrlAnalysisPayload, VideoUrlAnalysisRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.tagging.gemini_video_url import GeminiVideoUrlAnalyzer
from search_agent.utils.normalize import normalize_chinese_count


class VideoUrlAnalysisWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: VideoUrlAnalysisRunConfig,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.video_url_analysis")
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.analysis_store = JsonlStore(self.paths.video_url_analysis_output, VideoUrlAnalysisRecord)
        self.analyzer = GeminiVideoUrlAnalyzer(model_name=self.run_config.model_name)

    def run(self) -> RunSummary:
        self.paths.ensure_directories()
        discovery_records = self.discovery_store.load_all()
        latest_by_video_url: dict[str, CreatorDiscoveryRecord] = {}
        for record in discovery_records:
            video_url = (record.video_url or "").strip()
            if not video_url:
                continue
            latest_by_video_url[video_url] = record

        existing = self.analysis_store.load_all()
        processed_urls = {record.video_url for record in existing if record.video_url}
        candidates = list(latest_by_video_url.values())
        if not self.run_config.force:
            candidates = [record for record in candidates if (record.video_url or "") not in processed_urls]
        if self.run_config.max_items is not None:
            candidates = candidates[: self.run_config.max_items]

        processed = completed = skipped = blocked = 0
        start_time = time.monotonic()

        for record in candidates:
            processed += 1
            viral_snapshot = self._compute_viral_rule(record)
            try:
                payload = self.analyzer.analyze(record)
                output = self._build_output_record(
                    record=record,
                    payload=payload,
                    status=AnalysisStatus.COMPLETED,
                    backend="gemini",
                    error_text=None,
                    viral_snapshot=viral_snapshot,
                )
                completed += 1
            except Exception as exc:
                output = self._build_output_record(
                    record=record,
                    payload=None,
                    status=AnalysisStatus.FAILED,
                    backend="gemini",
                    error_text=str(exc),
                    viral_snapshot=viral_snapshot,
                )
                skipped += 1
                self.logger.warning(
                    "video-url analysis failed",
                    extra={
                        "record_id": record.record_id,
                        "video_url": record.video_url,
                        "error_text": str(exc),
                    },
                )

            self.analysis_store.upsert(output, key_field="video_url")

        duration_minutes = round((time.monotonic() - start_time) / 60, 2)
        return RunSummary(
            stage=WorkflowStage.VIDEO_URL_ANALYSIS,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=0,
            output_path=str(self.paths.video_url_analysis_output),
            queue_path=None,
        )

    @staticmethod
    def _compute_viral_rule(record: CreatorDiscoveryRecord) -> dict[str, int | bool | str | None]:
        share_count = normalize_chinese_count(record.share_count_raw)
        follower_count = record.follower_count_normalized or normalize_chinese_count(record.follower_count_raw)
        if share_count is not None and share_count > 100_000:
            return {
                "share_count": share_count,
                "follower_count": follower_count,
                "is_viral": True,
                "rule_hit": "share_gt_100k",
                "rule_reasoning": "转发量超过10万，按规则直接判定为爆款。",
            }
        if share_count is not None and share_count > 10_000 and follower_count is not None and follower_count < 300_000:
            return {
                "share_count": share_count,
                "follower_count": follower_count,
                "is_viral": True,
                "rule_hit": "share_gt_10k_and_followers_lt_300k",
                "rule_reasoning": "转发量过万且账号粉丝未破30万，按规则判定为爆款。",
            }
        return {
            "share_count": share_count,
            "follower_count": follower_count,
            "is_viral": False,
            "rule_hit": "no_rule_hit",
            "rule_reasoning": "未命中直接爆款规则，需要结合内容与互动做进一步判断。",
        }

    def _build_output_record(
        self,
        record: CreatorDiscoveryRecord,
        payload: VideoUrlAnalysisPayload | None,
        status: AnalysisStatus,
        backend: str,
        error_text: str | None,
        viral_snapshot: dict[str, int | bool | str | None],
    ) -> VideoUrlAnalysisRecord:
        return VideoUrlAnalysisRecord(
            record_id=record.record_id,
            creator_name=record.creator_name,
            collection_date=record.collection_date,
            video_url=record.video_url or "",
            analysis_status=status,
            analysis_backend=backend,
            analysis_model=self.run_config.model_name,
            share_count_raw=record.share_count_raw,
            follower_count_raw=record.follower_count_raw,
            share_count_normalized=viral_snapshot["share_count"],  # type: ignore[arg-type]
            follower_count_normalized=viral_snapshot["follower_count"],  # type: ignore[arg-type]
            is_viral=viral_snapshot["is_viral"],  # type: ignore[arg-type]
            viral_rule_hit=viral_snapshot["rule_hit"],  # type: ignore[arg-type]
            viral_rule_reasoning=viral_snapshot["rule_reasoning"],  # type: ignore[arg-type]
            video_access_status=payload.video_access_status if payload else None,
            theme=payload.theme if payload else None,
            protagonist=payload.protagonist if payload else None,
            scene=payload.scene if payload else None,
            core_action=payload.core_action if payload else None,
            action_highlights=payload.action_highlights if payload else [],
            encountered_people=payload.encountered_people if payload else [],
            people_story_traits=payload.people_story_traits if payload else [],
            visual_highlights=payload.visual_highlights if payload else [],
            tags=payload.tags if payload else [],
            retention_reasons=payload.retention_reasons if payload else [],
            interaction_reasons=payload.interaction_reasons if payload else [],
            opening_hook_analysis=payload.opening_hook_analysis if payload else None,
            audience_emotion=payload.audience_emotion if payload else None,
            core_audience=payload.core_audience if payload else None,
            replicability=payload.replicability if payload else None,
            replicability_reasoning=payload.replicability_reasoning if payload else None,
            series_continuation_interest=payload.series_continuation_interest if payload else None,
            analysis_reasoning=payload.analysis_reasoning if payload else None,
            analysis_error=error_text,
        )
