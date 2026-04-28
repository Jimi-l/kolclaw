from __future__ import annotations

from search_agent.adapters.douyin.doubao_video_analysis import DoubaoVideoAnalysisWorkflow
from search_agent.adapters.douyin.live_workflow import DouyinLiveWorkflow
from search_agent.adapters.douyin.mp4_file_uploads import DouyinMp4FileUploadWorkflow
from search_agent.adapters.douyin.mp4_links import DouyinMp4LinkWorkflow
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
from search_agent.enums import NextAction, RecordStatus, WorkflowStage
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.cli import build_parser


def _discovery_record(record_id: str, video_url: str, workflow_run_id: str | None) -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=record_id,
        workflow_run_id=workflow_run_id,
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/13",
        video_url=video_url,
        creator_name="创作者",
        duplicate_key=f"douyin::{record_id}",
        next_action=NextAction.CONTINUE,
    )


def _mp4_record(record_id: str, video_url: str, workflow_run_id: str | None) -> Mp4LinkRecord:
    return Mp4LinkRecord(
        record_id=record_id,
        workflow_run_id=workflow_run_id,
        video_url=video_url,
        creator_name="创作者",
        status="success",
        direct_mp4_url="https://v9-default.365yg.com/video.mp4",
        access_mode="external_direct",
        attempt_count=1,
        updated_at="2026-04-13T00:00:00+00:00",
    )


def _upload_record(record_id: str, video_url: str, workflow_run_id: str | None) -> Mp4FileUploadRecord:
    return Mp4FileUploadRecord(
        record_id=record_id,
        workflow_run_id=workflow_run_id,
        video_url=video_url,
        creator_name="创作者",
        status="success",
        file_id=f"file_{record_id}",
        attempt_count=1,
        updated_at="2026-04-13T00:00:00+00:00",
    )


def _summary(stage: WorkflowStage, success: int) -> RunSummary:
    return RunSummary(
        stage=stage,
        run_id="test",
        duration_minutes=0,
        processed_candidates=success,
        successful_records=success,
        skipped_items=0,
        blocked_items=0,
        next_stage_ready=success,
        output_path=None,
        queue_path=None,
    )


def test_run_id_filters_keep_live_records_separate_from_history(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).append(
        _discovery_record("history", "https://www.douyin.com/video/history", None)
    )
    JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).append(
        _discovery_record("live", "https://www.douyin.com/video/live", "run-1")
    )
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_record("history", "https://www.douyin.com/video/history", None))
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_record("live", "https://www.douyin.com/video/live", "run-1"))
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(
        _upload_record("history", "https://www.douyin.com/video/history", None)
    )
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(
        _upload_record("live", "https://www.douyin.com/video/live", "run-1")
    )

    mp4_pending = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin"),
        run_config=Mp4LinkRunConfig(workflow_run_id="run-1", force=True),
    )._pending_records()
    upload_pending = DouyinMp4FileUploadWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_FILES),
        run_config=Mp4FileUploadRunConfig(workflow_run_id="run-1", force=True),
        file_client_factory=lambda *_args: None,
    )._pending_records()
    analysis_pending = DoubaoVideoAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
        run_config=DoubaoVideoAnalysisRunConfig(workflow_run_id="run-1", force=True),
        client_factory=lambda *_args: None,
    )._pending_records()

    assert [record.record_id for record in mp4_pending] == ["live"]
    assert [record.record_id for record in upload_pending] == ["live"]
    assert [record.record_id for record in analysis_pending] == ["live"]


def test_live_workflow_defaults_to_visible_browser_and_pipeline_stays_headless() -> None:
    parser = build_parser()

    live_args = parser.parse_args(["douyin-live-workflow"])
    pipeline_args = parser.parse_args(["douyin-video-pipeline"])

    assert DouyinLiveWorkflowRunConfig().headless is False
    assert live_args.headless is False
    assert pipeline_args.headless is True


def test_live_workflow_processes_fresh_run_to_target(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)

    class FakeDiscoveryWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
            for index in range(2):
                store.append(_discovery_record(f"record-{index}", f"https://www.douyin.com/video/{index}", self.run_config.workflow_run_id))
            return _summary(WorkflowStage.CREATOR_DISCOVERY, 2)

    class FakeMp4Workflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            discovery = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord).load_all()
            store = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord)
            count = 0
            for record in discovery:
                if record.workflow_run_id == self.run_config.workflow_run_id:
                    store.upsert(_mp4_record(record.record_id, record.video_url or "", record.workflow_run_id), key_field="video_url")
                    count += 1
            return _summary(WorkflowStage.DOUYIN_MP4_LINKS, count)

    class FakeUploadWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            mp4_records = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord).load_all()
            store = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord)
            count = 0
            for record in mp4_records:
                if record.workflow_run_id == self.run_config.workflow_run_id:
                    store.upsert(_upload_record(record.record_id, record.video_url, record.workflow_run_id), key_field="video_url")
                    count += 1
            return _summary(WorkflowStage.DOUYIN_MP4_FILES, count)

    class FakeAnalysisWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            uploads = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord).load_all()
            store = JsonlStore(self.paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord)
            count = 0
            for upload in uploads:
                if upload.workflow_run_id == self.run_config.workflow_run_id:
                    store.upsert(
                        DoubaoVideoAnalysisRecord(
                            record_id=upload.record_id,
                            workflow_run_id=upload.workflow_run_id,
                            video_url=upload.video_url,
                            creator_name=upload.creator_name,
                            file_id=upload.file_id or "",
                            status="completed",
                            attempt_count=1,
                            updated_at="2026-04-13T00:00:00+00:00",
                        ),
                        key_field="video_url",
                    )
                    count += 1
            return _summary(WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS, count)

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinLiveWorkflowRunConfig(target_completed=2, batch_size=2, poll_seconds=0.01, stalled_round_limit=50),
        discovery_factory=FakeDiscoveryWorkflow,
        mp4_links_factory=FakeMp4Workflow,
        mp4_files_factory=FakeUploadWorkflow,
        doubao_analysis_factory=FakeAnalysisWorkflow,
    )

    summary = workflow.run()

    assert summary["exit_code"] == 0
    assert summary["stop_reason"] == "target_completed"
    assert summary["workflow_run_id"] == artifacts.run_id
    assert summary["stats"]["discovery_records"] == 2
    assert summary["stats"]["doubao_completed"] == 2
    assert summary["runnable_backlog"]["total"] == 0


def test_live_workflow_uses_discovery_multiplier_when_max_records_not_set(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)
    captured = {}

    class FakeDiscoveryWorkflow:
        def __init__(self, run_config, **_kwargs):
            self.run_config = run_config

        def run(self):
            captured["max_records"] = self.run_config.max_records
            return _summary(WorkflowStage.CREATOR_DISCOVERY, 0)

    class NoopWorkflow:
        def __init__(self, **_kwargs):
            pass

        def run(self):
            return _summary(WorkflowStage.DOUYIN_MP4_LINKS, 0)

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinLiveWorkflowRunConfig(
            target_completed=4,
            max_discovery_records=None,
            discovery_multiplier=3,
            poll_seconds=0.01,
            stalled_round_limit=1,
        ),
        discovery_factory=FakeDiscoveryWorkflow,
        mp4_links_factory=NoopWorkflow,
        mp4_files_factory=NoopWorkflow,
        doubao_analysis_factory=NoopWorkflow,
    )

    summary = workflow.run()

    assert captured["max_records"] == 12
    assert summary["exit_code"] == 1
    assert summary["stop_reason"] == "stalled_after_discovery"
    assert "no fresh discovery records were collected for this run" in summary["blockage_reasons"]


def test_live_workflow_respects_explicit_max_discovery_records(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)
    captured = {}

    class FakeDiscoveryWorkflow:
        def __init__(self, run_config, **_kwargs):
            self.run_config = run_config

        def run(self):
            captured["max_records"] = self.run_config.max_records
            return _summary(WorkflowStage.CREATOR_DISCOVERY, 0)

    class NoopWorkflow:
        def __init__(self, **_kwargs):
            pass

        def run(self):
            return _summary(WorkflowStage.DOUYIN_MP4_LINKS, 0)

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinLiveWorkflowRunConfig(
            target_completed=4,
            max_discovery_records=5,
            discovery_multiplier=3,
            poll_seconds=0.01,
            stalled_round_limit=1,
        ),
        discovery_factory=FakeDiscoveryWorkflow,
        mp4_links_factory=NoopWorkflow,
        mp4_files_factory=NoopWorkflow,
        doubao_analysis_factory=NoopWorkflow,
    )

    workflow.run()

    assert captured["max_records"] == 5


def test_live_workflow_uses_gate_size_but_downstream_processes_one_item_per_pass(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)
    captured_batch_sizes: dict[str, int] = {}

    class FakeDiscoveryWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
            for index in range(5):
                store.append(_discovery_record(f"record-{index}", f"https://www.douyin.com/video/{index}", self.run_config.workflow_run_id))
            return _summary(WorkflowStage.CREATOR_DISCOVERY, 5)

    class FakeMp4Workflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            captured_batch_sizes["mp4"] = self.run_config.batch_size
            discovery = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord).load_all()
            record = next(record for record in discovery if record.workflow_run_id == self.run_config.workflow_run_id)
            JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord).upsert(
                _mp4_record(record.record_id, record.video_url or "", record.workflow_run_id),
                key_field="video_url",
            )
            return _summary(WorkflowStage.DOUYIN_MP4_LINKS, 1)

    class FakeUploadWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            captured_batch_sizes["upload"] = self.run_config.batch_size
            return _summary(WorkflowStage.DOUYIN_MP4_FILES, 0)

    class FakeAnalysisWorkflow:
        def __init__(self, run_config, **_kwargs):
            self.run_config = run_config

        def run(self):
            captured_batch_sizes["analysis"] = self.run_config.batch_size
            return _summary(WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS, 0)

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinLiveWorkflowRunConfig(
            target_completed=5,
            batch_size=5,
            stage_item_batch_size=1,
            poll_seconds=0.01,
            max_minutes=0.01,
            stalled_round_limit=50,
        ),
        discovery_factory=FakeDiscoveryWorkflow,
        mp4_links_factory=FakeMp4Workflow,
        mp4_files_factory=FakeUploadWorkflow,
        doubao_analysis_factory=FakeAnalysisWorkflow,
    )

    summary = workflow.run()

    assert summary["stats"]["discovery_video_urls"] == 5
    assert captured_batch_sizes["mp4"] == 1
    assert captured_batch_sizes.get("upload") is None
    assert captured_batch_sizes.get("analysis") is None


def test_live_workflow_does_not_stall_while_upload_stage_is_running(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)
    upload_started = False

    class FakeDiscoveryWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
            store.append(_discovery_record("record-1", "https://www.douyin.com/video/1", self.run_config.workflow_run_id))
            return _summary(WorkflowStage.CREATOR_DISCOVERY, 1)

    class FakeMp4Workflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord).upsert(
                _mp4_record("record-1", "https://www.douyin.com/video/1", self.run_config.workflow_run_id),
                key_field="video_url",
            )
            return _summary(WorkflowStage.DOUYIN_MP4_LINKS, 1)

    class SlowUploadWorkflow:
        def __init__(self, paths, run_config, **_kwargs):
            self.paths = paths
            self.run_config = run_config

        def run(self):
            nonlocal upload_started
            upload_started = True
            JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord).upsert(
                Mp4FileUploadRecord(
                    record_id="record-1",
                    workflow_run_id=self.run_config.workflow_run_id,
                    video_url="https://www.douyin.com/video/1",
                    status="uploading",
                    attempt_count=1,
                    updated_at="2026-04-13T00:00:00+00:00",
                ),
                key_field="video_url",
            )
            import time

            time.sleep(0.05)
            return _summary(WorkflowStage.DOUYIN_MP4_FILES, 0)

    class NoopAnalysisWorkflow:
        def __init__(self, **_kwargs):
            pass

        def run(self):
            return _summary(WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS, 0)

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
            run_config=DouyinLiveWorkflowRunConfig(
                target_completed=1,
                max_minutes=0.01,
                poll_seconds=0.01,
                stalled_round_limit=1,
            ),
        discovery_factory=FakeDiscoveryWorkflow,
        mp4_links_factory=FakeMp4Workflow,
        mp4_files_factory=SlowUploadWorkflow,
        doubao_analysis_factory=NoopAnalysisWorkflow,
    )

    summary = workflow.run()

    assert upload_started is True
    assert summary["stop_reason"] == "max_minutes_reached"
    assert summary["in_flight"]["uploads_processing"] >= 1
