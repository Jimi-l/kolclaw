from __future__ import annotations

from search_agent.adapters.douyin.doubao_video_analysis import DoubaoVideoAnalysisWorkflow
from search_agent.adapters.douyin.mp4_file_uploads import DouyinMp4FileUploadWorkflow
from search_agent.adapters.douyin.mp4_links import DouyinMp4LinkWorkflow
from search_agent.adapters.douyin.video_pipeline import DouyinVideoPipelineWorkflow
from search_agent.artifacts import ArtifactManager
from search_agent.config import (
    BrowserConfig,
    DoubaoVideoAnalysisRunConfig,
    DouyinVideoPipelineRunConfig,
    Mp4FileUploadRunConfig,
    Mp4LinkRunConfig,
    RuntimePaths,
)
from search_agent.enums import NextAction, RecordStatus, WorkflowStage
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


def _run_summary(stage: WorkflowStage, successful: int = 0) -> RunSummary:
    return RunSummary(
        stage=stage,
        run_id="test-run",
        duration_minutes=0,
        processed_candidates=successful,
        successful_records=successful,
        skipped_items=0,
        blocked_items=0,
        next_stage_ready=successful,
        output_path=None,
        queue_path=None,
    )


def _pipeline(paths: RuntimePaths, run_config: DouyinVideoPipelineRunConfig, factories):
    return DouyinVideoPipelineWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_VIDEO_PIPELINE),
        run_config=run_config,
        mp4_links_factory=factories["mp4_links"],
        mp4_files_factory=factories["mp4_files"],
        doubao_analysis_factory=factories["doubao"],
    )


def _discovery(record_id: str, video_url: str) -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=record_id,
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/14",
        video_url=video_url,
        creator_name="创作者",
        duplicate_key=f"douyin::{record_id}",
        next_action=NextAction.CONTINUE,
    )


def _mp4(record_id: str, video_url: str, status: str = "success") -> Mp4LinkRecord:
    return Mp4LinkRecord(
        record_id=record_id,
        video_url=video_url,
        creator_name="创作者",
        status=status,  # type: ignore[arg-type]
        direct_mp4_url="https://v9-default.365yg.com/video.mp4" if status == "success" else None,
        final_url="https://v9-default.365yg.com/final.mp4" if status == "success" else None,
        access_mode="external_direct" if status == "success" else None,
        attempt_count=1,
        last_error=None if status == "success" else "boom",
        updated_at="2026-04-14T00:00:00+00:00",
    )


def _upload(record_id: str, video_url: str, status: str = "success") -> Mp4FileUploadRecord:
    return Mp4FileUploadRecord(
        record_id=record_id,
        video_url=video_url,
        creator_name="创作者",
        status=status,  # type: ignore[arg-type]
        direct_mp4_url="https://v9-default.365yg.com/video.mp4",
        final_url="https://v9-default.365yg.com/final.mp4",
        source_mp4_access_mode="external_direct",
        file_id="file_123" if status == "success" else None,
        attempt_count=1,
        last_error=None if status == "success" else "boom",
        updated_at="2026-04-14T00:00:00+00:00",
    )


def test_pipeline_runs_three_stages_in_order_and_stops_at_target(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    order = []

    class FakeWorkflow:
        def __init__(self, name, stage, mutate):
            self.name = name
            self.stage = stage
            self.mutate = mutate

        def run(self):
            order.append(self.name)
            self.mutate()
            return _run_summary(self.stage, successful=1)

    factories = {
        "mp4_links": lambda **_kwargs: FakeWorkflow(
            "mp4-links",
            WorkflowStage.DOUYIN_MP4_LINKS,
            lambda: JsonlStore(paths.mp4_links_output, Mp4LinkRecord).upsert(
                Mp4LinkRecord(
                    record_id="record-1",
                    video_url="https://www.douyin.com/video/1",
                    creator_name="创作者",
                    status="success",
                    direct_mp4_url="https://v9-default.365yg.com/video.mp4",
                    access_mode="external_direct",
                    attempt_count=1,
                    updated_at="2026-04-13T00:00:00+00:00",
                ),
                key_field="video_url",
            ),
        ),
        "mp4_files": lambda **_kwargs: FakeWorkflow(
            "mp4-files",
            WorkflowStage.DOUYIN_MP4_FILES,
            lambda: JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).upsert(
                Mp4FileUploadRecord(
                    record_id="record-1",
                    video_url="https://www.douyin.com/video/1",
                    creator_name="创作者",
                    status="success",
                    file_id="file_123",
                    attempt_count=1,
                    updated_at="2026-04-13T00:00:00+00:00",
                ),
                key_field="video_url",
            ),
        ),
        "doubao": lambda **_kwargs: FakeWorkflow(
            "doubao",
            WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS,
            lambda: JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).upsert(
                DoubaoVideoAnalysisRecord(
                    record_id="record-1",
                    video_url="https://www.douyin.com/video/1",
                    creator_name="创作者",
                    file_id="file_123",
                    status="completed",
                    attempt_count=1,
                    updated_at="2026-04-13T00:00:00+00:00",
                ),
                key_field="video_url",
            ),
        ),
    }

    summary = _pipeline(paths, DouyinVideoPipelineRunConfig(target_completed=1, batch_size=10), factories).run()

    assert order == ["mp4-links", "mp4-files", "doubao"]
    assert summary["exit_code"] == 0
    assert summary["stop_reason"] == "target_completed"
    assert summary["completed"] == 1


def test_pipeline_stops_without_running_when_target_already_met(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).append(
        DoubaoVideoAnalysisRecord(
            record_id="record-1",
            video_url="https://www.douyin.com/video/1",
            file_id="file_123",
            status="completed",
            attempt_count=1,
            updated_at="2026-04-13T00:00:00+00:00",
        )
    )
    factories = {
        "mp4_links": lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        "mp4_files": lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
        "doubao": lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    }

    summary = _pipeline(paths, DouyinVideoPipelineRunConfig(target_completed=1), factories).run()

    assert summary["exit_code"] == 0
    assert summary["stop_reason"] == "target_already_met"
    assert summary["rounds_run"] == 0


def test_pipeline_defaults_retry_failed_without_force(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    captured = []

    class FakeWorkflow:
        def __init__(self, stage):
            self.stage = stage

        def run(self):
            return _run_summary(self.stage)

    def capture_factory(stage):
        def factory(**kwargs):
            captured.append(kwargs["run_config"])
            return FakeWorkflow(stage)

        return factory

    factories = {
        "mp4_links": capture_factory(WorkflowStage.DOUYIN_MP4_LINKS),
        "mp4_files": capture_factory(WorkflowStage.DOUYIN_MP4_FILES),
        "doubao": capture_factory(WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
    }

    _pipeline(paths, DouyinVideoPipelineRunConfig(target_completed=1, max_rounds=1), factories).run()

    assert len(captured) == 3
    assert all(config.retry_failed is True for config in captured)
    assert all(config.force is False for config in captured)


def test_history_backfill_skips_success_retries_failed_and_force_reprocesses_success(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()

    success_url = "https://www.douyin.com/video/success"
    failed_url = "https://www.douyin.com/video/failed"
    processing_url = "https://www.douyin.com/video/processing"
    upload_failed_url = "https://www.douyin.com/video/upload-failed"
    uploading_url = "https://www.douyin.com/video/uploading"

    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    for record_id, video_url in (
        ("success", success_url),
        ("failed", failed_url),
        ("processing", processing_url),
        ("upload-failed", upload_failed_url),
        ("uploading", uploading_url),
    ):
        discovery_store.append(_discovery(record_id, video_url))

    mp4_store = JsonlStore(paths.mp4_links_output, Mp4LinkRecord)
    mp4_store.append(_mp4("success", success_url, status="success"))
    mp4_store.append(_mp4("failed", failed_url, status="failed"))
    mp4_store.append(_mp4("processing", processing_url, status="processing"))
    mp4_store.append(_mp4("upload-failed", upload_failed_url, status="success"))
    mp4_store.append(_mp4("uploading", uploading_url, status="success"))

    upload_store = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord)
    upload_store.append(_upload("success", success_url, status="success"))
    upload_store.append(_upload("processing", processing_url, status="success"))
    upload_store.append(_upload("upload-failed", upload_failed_url, status="failed"))
    upload_store.append(_upload("uploading", uploading_url, status="uploading"))

    JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).append(
        DoubaoVideoAnalysisRecord(
            record_id="success",
            video_url=success_url,
            creator_name="创作者",
            file_id="file_123",
            status="completed",
            attempt_count=1,
            updated_at="2026-04-14T00:00:00+00:00",
        )
    )
    JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).append(
        DoubaoVideoAnalysisRecord(
            record_id="processing",
            video_url=processing_url,
            creator_name="创作者",
            file_id="file_123",
            status="processing",
            attempt_count=1,
            updated_at="2026-04-14T00:00:00+00:00",
        )
    )

    mp4_pending = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin", headless=True),
        run_config=Mp4LinkRunConfig(retry_failed=True, force=False),
    )._pending_records()
    upload_pending = DouyinMp4FileUploadWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_FILES),
        run_config=Mp4FileUploadRunConfig(retry_failed=True, force=False),
        file_client_factory=lambda *_args: object(),
    )._pending_records()
    analysis_pending = DoubaoVideoAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
        run_config=DoubaoVideoAnalysisRunConfig(retry_failed=True, force=False),
        client_factory=lambda *_args: object(),
    )._pending_records()

    assert [record.record_id for record in mp4_pending] == ["failed", "processing"]
    assert [record.record_id for record in upload_pending] == ["upload-failed", "uploading"]
    assert [record.record_id for record in analysis_pending] == ["processing"]

    forced_mp4_pending = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin", headless=True),
        run_config=Mp4LinkRunConfig(retry_failed=True, force=True),
    )._pending_records()
    forced_upload_pending = DouyinMp4FileUploadWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_FILES),
        run_config=Mp4FileUploadRunConfig(retry_failed=True, force=True),
        file_client_factory=lambda *_args: object(),
    )._pending_records()
    forced_analysis_pending = DoubaoVideoAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
        run_config=DoubaoVideoAnalysisRunConfig(retry_failed=True, force=True),
        client_factory=lambda *_args: object(),
    )._pending_records()

    assert success_url in {record.video_url for record in forced_mp4_pending}
    assert success_url in {record.video_url for record in forced_upload_pending}
    assert success_url in {record.video_url for record in forced_analysis_pending}


def test_pipeline_returns_no_progress_summary(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()

    class FakeWorkflow:
        def __init__(self, stage):
            self.stage = stage

        def run(self):
            return _run_summary(self.stage)

    factories = {
        "mp4_links": lambda **_kwargs: FakeWorkflow(WorkflowStage.DOUYIN_MP4_LINKS),
        "mp4_files": lambda **_kwargs: FakeWorkflow(WorkflowStage.DOUYIN_MP4_FILES),
        "doubao": lambda **_kwargs: FakeWorkflow(WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
    }

    summary = _pipeline(paths, DouyinVideoPipelineRunConfig(target_completed=1, max_rounds=1), factories).run()

    assert summary["exit_code"] == 1
    assert summary["stop_reason"] == "no_progress"
    assert summary["stats"]["doubao_completed"] == 0
