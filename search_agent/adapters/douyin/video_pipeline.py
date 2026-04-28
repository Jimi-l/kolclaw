from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from search_agent.artifacts import ArtifactManager
from search_agent.config import (
    BrowserConfig,
    DoubaoVideoAnalysisRunConfig,
    DouyinVideoPipelineRunConfig,
    Mp4FileUploadRunConfig,
    Mp4LinkRunConfig,
    RuntimePaths,
)
from search_agent.enums import WorkflowStage
from search_agent.models.common import RunSummary
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


WorkflowFactory = Callable[..., Any]


class DouyinVideoPipelineWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: DouyinVideoPipelineRunConfig,
        mp4_links_factory: WorkflowFactory | None = None,
        mp4_files_factory: WorkflowFactory | None = None,
        doubao_analysis_factory: WorkflowFactory | None = None,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.video_pipeline")
        self.mp4_links_factory = mp4_links_factory or _build_mp4_links_workflow
        self.mp4_files_factory = mp4_files_factory or _build_mp4_files_workflow
        self.doubao_analysis_factory = doubao_analysis_factory or _build_doubao_analysis_workflow
        self.mp4_store = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord)
        self.upload_store = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord)
        self.analysis_store = JsonlStore(self.paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord)

    def run(self) -> dict:
        self.paths.ensure_directories()
        start_time = time.monotonic()
        initial_completed = self._completed_count()
        target_completed = max(self.run_config.target_completed, 0)
        rounds: list[dict] = []

        if initial_completed >= target_completed:
            return self._build_summary(start_time, rounds, initial_completed, "target_already_met", exit_code=0)

        previous_stats = self._stats()
        for round_index in range(1, max(self.run_config.max_rounds, 0) + 1):
            self.logger.info("starting douyin video pipeline round", extra={"round": round_index})

            mp4_links_summary = self._run_mp4_links()
            mp4_files_summary = self._run_mp4_files()
            doubao_summary = self._run_doubao_analysis()
            stats = self._stats()
            completed = stats["doubao_completed"]
            progress = _progress_delta(previous_stats, stats)
            round_payload = {
                "round": round_index,
                "progress": progress,
                "stats": stats,
                "mp4_links": mp4_links_summary,
                "mp4_files": mp4_files_summary,
                "doubao_analysis": doubao_summary,
            }
            rounds.append(round_payload)

            if completed >= target_completed:
                return self._build_summary(start_time, rounds, completed, "target_completed", exit_code=0)
            if not _has_progress(progress):
                return self._build_summary(start_time, rounds, completed, "no_progress", exit_code=1)
            previous_stats = stats
            time.sleep(max(self.run_config.poll_seconds, 0))

        return self._build_summary(start_time, rounds, self._completed_count(), "max_rounds_reached", exit_code=1)

    def _run_mp4_links(self) -> dict:
        workflow = self.mp4_links_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            browser_config=BrowserConfig(
                site_name="douyin",
                headless=self.run_config.headless,
                channel=self.run_config.browser_channel,
            ),
            run_config=Mp4LinkRunConfig(
                batch_size=self.run_config.batch_size,
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=self.run_config.force,
                max_batches=1,
                page_wait_ms=self.run_config.page_wait_ms,
            ),
        )
        return _summary_payload(workflow.run())

    def _run_mp4_files(self) -> dict:
        workflow = self.mp4_files_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            run_config=Mp4FileUploadRunConfig(
                batch_size=self.run_config.batch_size,
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=self.run_config.force,
                max_batches=1,
                ark_base_url=self.run_config.ark_base_url,
            ),
        )
        return _summary_payload(workflow.run())

    def _run_doubao_analysis(self) -> dict:
        workflow = self.doubao_analysis_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            run_config=DoubaoVideoAnalysisRunConfig(
                batch_size=self.run_config.batch_size,
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=self.run_config.force,
                max_batches=1,
                model_name=self.run_config.model_name,
                ark_base_url=self.run_config.ark_base_url,
                max_output_tokens=self.run_config.max_output_tokens,
            ),
        )
        return _summary_payload(workflow.run())

    def _completed_count(self) -> int:
        return sum(1 for record in self.analysis_store.load_all() if record.status == "completed")

    def _stats(self) -> dict[str, int]:
        mp4_records = self.mp4_store.load_all()
        upload_records = self.upload_store.load_all()
        analysis_records = self.analysis_store.load_all()
        return {
            "mp4_external_direct_success": sum(
                1 for record in mp4_records if record.status == "success" and record.access_mode == "external_direct"
            ),
            "mp4_failed": sum(1 for record in mp4_records if record.status == "failed"),
            "mp4_processing": sum(1 for record in mp4_records if record.status == "processing"),
            "uploads_success": sum(1 for record in upload_records if record.status == "success" and record.file_id),
            "uploads_failed": sum(1 for record in upload_records if record.status == "failed"),
            "uploads_processing": sum(1 for record in upload_records if record.status in {"downloading", "uploading"}),
            "doubao_completed": sum(1 for record in analysis_records if record.status == "completed"),
            "doubao_failed": sum(1 for record in analysis_records if record.status == "failed"),
            "doubao_processing": sum(1 for record in analysis_records if record.status == "processing"),
        }

    def _build_summary(
        self,
        start_time: float,
        rounds: list[dict],
        completed: int,
        stop_reason: str,
        exit_code: int,
    ) -> dict:
        return {
            "stage": WorkflowStage.DOUYIN_VIDEO_PIPELINE.value,
            "run_id": self.artifacts.run_id,
            "duration_minutes": round((time.monotonic() - start_time) / 60, 2),
            "target_completed": self.run_config.target_completed,
            "completed": completed,
            "rounds_run": len(rounds),
            "stop_reason": stop_reason,
            "exit_code": exit_code,
            "stats": self._stats(),
            "rounds": rounds,
            "output_path": str(self.paths.doubao_video_analysis_output),
        }


def _build_mp4_links_workflow(**kwargs):
    from search_agent.adapters.douyin.mp4_links import DouyinMp4LinkWorkflow

    return DouyinMp4LinkWorkflow(**kwargs)


def _build_mp4_files_workflow(**kwargs):
    from search_agent.adapters.douyin.mp4_file_uploads import DouyinMp4FileUploadWorkflow

    return DouyinMp4FileUploadWorkflow(**kwargs)


def _build_doubao_analysis_workflow(**kwargs):
    from search_agent.adapters.douyin.doubao_video_analysis import DoubaoVideoAnalysisWorkflow

    return DoubaoVideoAnalysisWorkflow(**kwargs)


def _summary_payload(summary: Any) -> dict:
    if isinstance(summary, RunSummary):
        return summary.model_dump(mode="json")
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")
    if isinstance(summary, dict):
        return summary
    return {"summary": str(summary)}


def _progress_delta(previous: dict[str, int], current: dict[str, int]) -> dict[str, int]:
    return {key: current.get(key, 0) - previous.get(key, 0) for key in current}


def _has_progress(progress: dict[str, int]) -> bool:
    return any(
        progress.get(key, 0) > 0
        for key in (
            "mp4_external_direct_success",
            "uploads_success",
            "doubao_completed",
            "mp4_failed",
            "uploads_failed",
            "doubao_failed",
        )
    )
