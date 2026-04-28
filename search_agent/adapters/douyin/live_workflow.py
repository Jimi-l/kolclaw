from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from search_agent.artifacts import ArtifactManager
from search_agent.config import (
    BrowserConfig,
    DiscoveryRunConfig,
    DoubaoVideoAnalysisRunConfig,
    DouyinLiveWorkflowRunConfig,
    Mp4FileUploadRunConfig,
    Mp4LinkRunConfig,
    RuntimePaths,
)
from search_agent.enums import WorkflowStage
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


WorkflowFactory = Callable[..., Any]


class DouyinLiveWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: DouyinLiveWorkflowRunConfig,
        discovery_factory: WorkflowFactory | None = None,
        mp4_links_factory: WorkflowFactory | None = None,
        mp4_files_factory: WorkflowFactory | None = None,
        doubao_analysis_factory: WorkflowFactory | None = None,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.workflow_run_id = artifacts.run_id
        self.logger = logging.getLogger("search_agent.live_workflow")
        self.stop_event = threading.Event()
        self._active_lock = threading.Lock()
        self._active_stages: set[str] = set()
        self.discovery_factory = discovery_factory or _build_discovery_workflow
        self.mp4_links_factory = mp4_links_factory or _build_mp4_links_workflow
        self.mp4_files_factory = mp4_files_factory or _build_mp4_files_workflow
        self.doubao_analysis_factory = doubao_analysis_factory or _build_doubao_analysis_workflow
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.mp4_store = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord)
        self.upload_store = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord)
        self.analysis_store = JsonlStore(self.paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord)

    def run(self) -> dict:
        self.paths.ensure_directories()
        start_time = time.monotonic()
        deadline = start_time + self.run_config.max_minutes * 60 if self.run_config.max_minutes > 0 else None
        stage_summaries: dict[str, list[dict]] = {"discovery": [], "mp4_links": [], "mp4_files": [], "doubao_analysis": []}
        errors: list[dict] = []
        discovery_done = threading.Event()

        discovery_thread = threading.Thread(
            target=self._run_discovery,
            args=(stage_summaries, errors, discovery_done),
            name="douyin-live-discovery",
            daemon=True,
        )
        mp4_links_thread = threading.Thread(
            target=self._stage_loop,
            args=("mp4_links", self._run_mp4_links_once, stage_summaries, errors, deadline),
            name="douyin-live-mp4-links",
            daemon=True,
        )
        upload_thread = threading.Thread(
            target=self._stage_loop,
            args=("mp4_files", self._run_mp4_files_once, stage_summaries, errors, deadline),
            name="douyin-live-mp4-files",
            daemon=True,
        )
        analysis_thread = threading.Thread(
            target=self._stage_loop,
            args=("doubao_analysis", self._run_doubao_analysis_once, stage_summaries, errors, deadline),
            name="douyin-live-doubao-analysis",
            daemon=True,
        )

        discovery_thread.start()
        mp4_links_thread.start()
        upload_thread.start()
        analysis_thread.start()

        stalled_rounds = 0
        previous_progress_stats = self._progress_stats(self._snapshot())
        stop_reason = "unknown"

        while True:
            if self._target_met() and not self.run_config.watch:
                stop_reason = "target_completed"
                self.stop_event.set()
                break
            if deadline is not None and time.monotonic() >= deadline:
                stop_reason = "max_minutes_reached"
                self.stop_event.set()
                break

            snapshot = self._snapshot()
            progress_stats = self._progress_stats(snapshot)
            if progress_stats == previous_progress_stats:
                stalled_rounds += 1
            else:
                stalled_rounds = 0
            previous_progress_stats = progress_stats

            if (
                not self.run_config.watch
                and discovery_done.is_set()
                and stalled_rounds >= self.run_config.stalled_round_limit
                and not self._has_in_flight(snapshot)
                and not self._has_runnable_backlog(snapshot)
                and not self._target_met()
            ):
                stop_reason = "stalled_after_discovery"
                self.stop_event.set()
                break

            time.sleep(max(self.run_config.poll_seconds, 0.1))

        discovery_thread.join(timeout=10)
        mp4_links_thread.join(timeout=10)
        upload_thread.join(timeout=10)
        analysis_thread.join(timeout=10)
        completed = self._completed_count()
        final_snapshot = self._snapshot()
        return {
            "stage": WorkflowStage.DOUYIN_LIVE_WORKFLOW.value,
            "run_id": self.artifacts.run_id,
            "workflow_run_id": self.workflow_run_id,
            "duration_minutes": round((time.monotonic() - start_time) / 60, 2),
            "target_completed": self.run_config.target_completed,
            "completed": completed,
            "stop_reason": stop_reason,
            "exit_code": 0 if (self.run_config.watch or completed >= self.run_config.target_completed) else 1,
            "stats": final_snapshot["stats"],
            "runnable_backlog": final_snapshot["runnable_backlog"],
            "in_flight": final_snapshot["in_flight"],
            "blockage_reasons": self._blockage_reasons(final_snapshot),
            "stage_summaries": stage_summaries,
            "errors": errors,
            "output_path": str(self.paths.doubao_video_analysis_output),
        }

    def _run_discovery(self, stage_summaries: dict[str, list[dict]], errors: list[dict], done: threading.Event) -> None:
        self._stage_started("discovery")
        try:
            workflow = self.discovery_factory(
                paths=self.paths,
                artifacts=self.artifacts,
                browser_config=BrowserConfig(
                    site_name="douyin",
                    headless=self.run_config.headless,
                    channel=self.run_config.browser_channel,
                ),
                run_config=DiscoveryRunConfig(
                    max_records=self._effective_max_discovery_records(),
                    max_minutes=self.run_config.max_minutes,
                    max_candidates=self.run_config.max_discovery_candidates,
                    content_analysis_enabled=False,
                    workflow_run_id=self.workflow_run_id,
                    stop_event=self.stop_event,
                ),
            )
            stage_summaries["discovery"].append(_summary_payload(workflow.run()))
        except Exception as exc:
            errors.append({"stage": "discovery", "error": str(exc)})
            self.logger.warning("live workflow discovery stage failed", extra={"error_text": str(exc)})
        finally:
            self._stage_finished("discovery")
            done.set()

    def _stage_loop(
        self,
        stage_name: str,
        run_once,
        stage_summaries: dict[str, list[dict]],
        errors: list[dict],
        deadline: float | None,
    ) -> None:
        while not self.stop_event.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                self.stop_event.set()
                break
            if not self._stage_should_run(stage_name):
                time.sleep(max(self.run_config.poll_seconds, 0.1))
                continue
            self._stage_started(stage_name)
            try:
                stage_summaries[stage_name].append(run_once())
            except Exception as exc:
                errors.append({"stage": stage_name, "error": str(exc)})
                self.logger.warning("live workflow stage failed", extra={"stage_name": stage_name, "error_text": str(exc)})
            finally:
                self._stage_finished(stage_name)
            time.sleep(max(self.run_config.poll_seconds, 0.1))

    def _stage_started(self, stage_name: str) -> None:
        with self._active_lock:
            self._active_stages.add(stage_name)

    def _stage_finished(self, stage_name: str) -> None:
        with self._active_lock:
            self._active_stages.discard(stage_name)

    def _active_stage_names(self) -> list[str]:
        with self._active_lock:
            return sorted(self._active_stages)

    def _effective_max_discovery_records(self) -> int:
        if self.run_config.max_discovery_records is not None:
            return max(self.run_config.max_discovery_records, 0)
        multiplier = max(self.run_config.discovery_multiplier, 1)
        return max(self.run_config.target_completed, 1) * multiplier

    def _stage_should_run(self, stage_name: str) -> bool:
        snapshot = self._snapshot()
        backlog = snapshot["runnable_backlog"]
        stats = snapshot["stats"]
        gate_size = self._gate_size()
        if stage_name == "mp4_links":
            return backlog["mp4_pending"] > 0 and stats["discovery_video_urls"] >= gate_size
        if stage_name == "mp4_files":
            return backlog["upload_pending"] > 0 and stats["mp4_external_direct_success"] >= gate_size
        if stage_name == "doubao_analysis":
            return backlog["doubao_pending"] > 0 and stats["uploads_success"] >= gate_size
        return True

    def _gate_size(self) -> int:
        return max(
            1,
            min(
                max(self.run_config.batch_size, 1),
                max(self.run_config.target_completed, 1),
                max(self._effective_max_discovery_records(), 1),
            ),
        )

    def _run_mp4_links_once(self) -> dict:
        workflow = self.mp4_links_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            browser_config=BrowserConfig(
                site_name=f"douyin_mp4_{self.workflow_run_id}",
                headless=self.run_config.headless,
                channel=self.run_config.browser_channel,
            ),
            run_config=Mp4LinkRunConfig(
                batch_size=max(self.run_config.stage_item_batch_size, 1),
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=False,
                max_batches=1,
                page_wait_ms=self.run_config.page_wait_ms,
                workflow_run_id=self.workflow_run_id,
            ),
        )
        return _summary_payload(workflow.run())

    def _run_mp4_files_once(self) -> dict:
        workflow = self.mp4_files_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            run_config=Mp4FileUploadRunConfig(
                batch_size=max(self.run_config.stage_item_batch_size, 1),
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=False,
                max_batches=1,
                poll_seconds=self.run_config.poll_seconds,
                ark_base_url=self.run_config.ark_base_url,
                workflow_run_id=self.workflow_run_id,
            ),
        )
        return _summary_payload(workflow.run())

    def _run_doubao_analysis_once(self) -> dict:
        workflow = self.doubao_analysis_factory(
            paths=self.paths,
            artifacts=self.artifacts,
            run_config=DoubaoVideoAnalysisRunConfig(
                batch_size=max(self.run_config.stage_item_batch_size, 1),
                watch=False,
                retry_failed=self.run_config.retry_failed,
                force=False,
                max_batches=1,
                poll_seconds=self.run_config.poll_seconds,
                model_name=self.run_config.model_name,
                ark_base_url=self.run_config.ark_base_url,
                max_output_tokens=self.run_config.max_output_tokens,
                workflow_run_id=self.workflow_run_id,
            ),
        )
        return _summary_payload(workflow.run())

    def _target_met(self) -> bool:
        return self._completed_count() >= self.run_config.target_completed

    def _completed_count(self) -> int:
        return sum(
            1
            for record in self.analysis_store.load_all()
            if record.workflow_run_id == self.workflow_run_id and record.status == "completed"
        )

    def _stats(self) -> dict[str, int]:
        discovery_records = self.discovery_store.load_all()
        mp4_records = self.mp4_store.load_all()
        upload_records = self.upload_store.load_all()
        analysis_records = self.analysis_store.load_all()
        return self._stats_from_records(discovery_records, mp4_records, upload_records, analysis_records)

    def _snapshot(self) -> dict[str, Any]:
        discovery_records = self.discovery_store.load_all()
        mp4_records = self.mp4_store.load_all()
        upload_records = self.upload_store.load_all()
        analysis_records = self.analysis_store.load_all()
        stats = self._stats_from_records(discovery_records, mp4_records, upload_records, analysis_records)
        runnable_backlog = self._runnable_backlog(discovery_records, mp4_records, upload_records, analysis_records)
        in_flight = {
            "active_stages": self._active_stage_names(),
            "mp4_processing": stats["mp4_processing"],
            "uploads_processing": stats["uploads_processing"],
            "doubao_processing": stats["doubao_processing"],
            "total": 0,
        }
        in_flight["total"] = (
            len(in_flight["active_stages"])
            + in_flight["mp4_processing"]
            + in_flight["uploads_processing"]
            + in_flight["doubao_processing"]
        )
        return {
            "stats": stats,
            "runnable_backlog": runnable_backlog,
            "in_flight": in_flight,
        }

    def _stats_from_records(
        self,
        discovery_records: list[CreatorDiscoveryRecord],
        mp4_records: list[Mp4LinkRecord],
        upload_records: list[Mp4FileUploadRecord],
        analysis_records: list[DoubaoVideoAnalysisRecord],
    ) -> dict[str, int]:
        return {
            "discovery_records": sum(1 for record in discovery_records if record.workflow_run_id == self.workflow_run_id),
            "discovery_video_urls": sum(
                1
                for record in discovery_records
                if record.workflow_run_id == self.workflow_run_id and bool((record.video_url or "").strip())
            ),
            "mp4_external_direct_success": sum(
                1
                for record in mp4_records
                if record.workflow_run_id == self.workflow_run_id
                and record.status == "success"
                and record.access_mode == "external_direct"
            ),
            "mp4_failed": sum(1 for record in mp4_records if record.workflow_run_id == self.workflow_run_id and record.status == "failed"),
            "mp4_processing": sum(
                1 for record in mp4_records if record.workflow_run_id == self.workflow_run_id and record.status == "processing"
            ),
            "uploads_success": sum(
                1
                for record in upload_records
                if record.workflow_run_id == self.workflow_run_id and record.status == "success" and record.file_id
            ),
            "uploads_failed": sum(1 for record in upload_records if record.workflow_run_id == self.workflow_run_id and record.status == "failed"),
            "uploads_processing": sum(
                1
                for record in upload_records
                if record.workflow_run_id == self.workflow_run_id and record.status in {"downloading", "uploading"}
            ),
            "doubao_completed": sum(
                1 for record in analysis_records if record.workflow_run_id == self.workflow_run_id and record.status == "completed"
            ),
            "doubao_failed": sum(
                1 for record in analysis_records if record.workflow_run_id == self.workflow_run_id and record.status == "failed"
            ),
            "doubao_processing": sum(
                1 for record in analysis_records if record.workflow_run_id == self.workflow_run_id and record.status == "processing"
            ),
        }

    def _runnable_backlog(
        self,
        discovery_records: list[CreatorDiscoveryRecord],
        mp4_records: list[Mp4LinkRecord],
        upload_records: list[Mp4FileUploadRecord],
        analysis_records: list[DoubaoVideoAnalysisRecord],
    ) -> dict[str, int]:
        mp4_by_url = {
            record.video_url: record for record in mp4_records if record.workflow_run_id == self.workflow_run_id
        }
        upload_by_url = {
            record.video_url: record for record in upload_records if record.workflow_run_id == self.workflow_run_id
        }
        analysis_by_url = {
            record.video_url: record for record in analysis_records if record.workflow_run_id == self.workflow_run_id
        }

        mp4_pending = 0
        for record in discovery_records:
            if record.workflow_run_id != self.workflow_run_id or not record.video_url:
                continue
            existing = mp4_by_url.get(record.video_url)
            if existing is None or self._retryable_mp4(existing):
                mp4_pending += 1

        upload_pending = 0
        for record in mp4_records:
            if record.workflow_run_id != self.workflow_run_id or not self._is_uploadable_mp4(record):
                continue
            existing = upload_by_url.get(record.video_url)
            if existing is None or self._retryable_upload(existing):
                upload_pending += 1

        analysis_pending = 0
        for record in upload_records:
            if record.workflow_run_id != self.workflow_run_id or record.status != "success" or not record.file_id:
                continue
            existing = analysis_by_url.get(record.video_url)
            if existing is None or self._retryable_analysis(existing):
                analysis_pending += 1

        return {
            "mp4_pending": mp4_pending,
            "upload_pending": upload_pending,
            "doubao_pending": analysis_pending,
            "total": mp4_pending + upload_pending + analysis_pending,
        }

    def _retryable_mp4(self, record: Mp4LinkRecord) -> bool:
        if record.status == "success":
            return False
        return self.run_config.retry_failed and record.status in {"failed", "processing"}

    def _retryable_upload(self, record: Mp4FileUploadRecord) -> bool:
        if record.status == "success":
            return False
        return self.run_config.retry_failed and record.status in {"failed", "downloading", "uploading"}

    def _retryable_analysis(self, record: DoubaoVideoAnalysisRecord) -> bool:
        if record.status == "completed":
            return False
        return self.run_config.retry_failed and record.status in {"failed", "processing"}

    @staticmethod
    def _is_uploadable_mp4(record: Mp4LinkRecord) -> bool:
        return record.status == "success" and record.access_mode == "external_direct" and bool(record.final_url or record.direct_mp4_url)

    @staticmethod
    def _progress_stats(snapshot: dict[str, Any]) -> dict[str, int]:
        stats = snapshot["stats"]
        return {
            "discovery_records": stats["discovery_records"],
            "discovery_video_urls": stats["discovery_video_urls"],
            "mp4_external_direct_success": stats["mp4_external_direct_success"],
            "mp4_failed": stats["mp4_failed"],
            "uploads_success": stats["uploads_success"],
            "uploads_failed": stats["uploads_failed"],
            "doubao_completed": stats["doubao_completed"],
            "doubao_failed": stats["doubao_failed"],
        }

    @staticmethod
    def _has_in_flight(snapshot: dict[str, Any]) -> bool:
        return snapshot["in_flight"]["total"] > 0

    @staticmethod
    def _has_runnable_backlog(snapshot: dict[str, Any]) -> bool:
        return snapshot["runnable_backlog"]["total"] > 0

    def _blockage_reasons(self, snapshot: dict[str, Any]) -> list[str]:
        stats = snapshot["stats"]
        backlog = snapshot["runnable_backlog"]
        in_flight = snapshot["in_flight"]
        reasons: list[str] = []
        if in_flight["uploads_processing"]:
            reasons.append("mp4 upload/download still in progress")
        if in_flight["doubao_processing"]:
            reasons.append("doubao analysis still in progress")
        if stats["mp4_failed"] and not backlog["mp4_pending"]:
            reasons.append("mp4 external-direct links are insufficient or failed")
        if stats["uploads_failed"] and not backlog["upload_pending"]:
            reasons.append("mp4 file uploads failed or are unavailable")
        if stats["doubao_failed"] and not backlog["doubao_pending"]:
            reasons.append("doubao analysis failed or returned incompatible output")
        if not reasons and backlog["total"]:
            gate_size = self._gate_size()
            if backlog["mp4_pending"] and stats["discovery_video_urls"] < gate_size:
                reasons.append(f"waiting for discovery gate: {stats['discovery_video_urls']}/{gate_size} video URLs")
            elif backlog["upload_pending"] and stats["mp4_external_direct_success"] < gate_size:
                reasons.append(f"waiting for MP4 gate: {stats['mp4_external_direct_success']}/{gate_size} external-direct links")
            elif backlog["doubao_pending"] and stats["uploads_success"] < gate_size:
                reasons.append(f"waiting for upload gate: {stats['uploads_success']}/{gate_size} uploaded files")
            else:
                reasons.append("runnable backlog remains but no progress was observed")
        if not reasons and stats["discovery_records"] == 0:
            reasons.append("no fresh discovery records were collected for this run")
        if not reasons and not self._target_met():
            reasons.append("target was not reached before the workflow stopped")
        return reasons


def _build_discovery_workflow(**kwargs):
    from search_agent.adapters.douyin.workflow import CreatorDiscoveryWorkflow

    return CreatorDiscoveryWorkflow(**kwargs)


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
    if hasattr(summary, "model_dump"):
        return summary.model_dump(mode="json")
    if isinstance(summary, dict):
        return summary
    return {"summary": str(summary)}
