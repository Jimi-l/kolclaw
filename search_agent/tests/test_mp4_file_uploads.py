from __future__ import annotations

from types import SimpleNamespace

from search_agent.adapters.douyin.mp4_file_uploads import DouyinMp4FileUploadWorkflow
from search_agent.artifacts import ArtifactManager
from search_agent.config import Mp4FileUploadRunConfig, RuntimePaths
from search_agent.enums import WorkflowStage
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


def _mp4_link(
    video_url: str,
    status: str = "success",
    access_mode: str | None = "external_direct",
    record_id: str = "record-1",
) -> Mp4LinkRecord:
    return Mp4LinkRecord(
        record_id=record_id,
        video_url=video_url,
        creator_name="创作者",
        status=status,  # type: ignore[arg-type]
        direct_mp4_url="https://v9-default.365yg.com/video.mp4",
        final_url="https://v9-default.365yg.com/final.mp4",
        source="download_addr",
        access_mode=access_mode,  # type: ignore[arg-type]
        content_type="video/mp4",
        content_length="2048",
        attempt_count=1,
        last_error=None,
        updated_at="2026-04-13T00:00:00+00:00",
    )


def _workflow(paths: RuntimePaths, run_config: Mp4FileUploadRunConfig | None = None, file_client_factory=None):
    return DouyinMp4FileUploadWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_FILES),
        run_config=run_config or Mp4FileUploadRunConfig(batch_size=10),
        file_client_factory=file_client_factory,
    )


def test_pending_records_only_uploads_external_direct_success(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    mp4_store = JsonlStore(paths.mp4_links_output, Mp4LinkRecord)
    mp4_store.append(_mp4_link("https://www.douyin.com/video/1", record_id="ok"))
    mp4_store.append(_mp4_link("https://www.douyin.com/video/2", access_mode="browser_context_only", record_id="context-only"))
    mp4_store.append(_mp4_link("https://www.douyin.com/video/3", status="failed", record_id="failed"))

    pending = _workflow(paths)._pending_records()

    assert [record.record_id for record in pending] == ["ok"]


def test_pending_records_skip_success_and_retry_failed_only_when_enabled(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    video_url = "https://www.douyin.com/video/1"
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_link(video_url))
    upload_store = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord)
    upload_store.append(
        Mp4FileUploadRecord(
            record_id="record-1",
            video_url=video_url,
            creator_name="创作者",
            status="failed",
            direct_mp4_url="https://v9-default.365yg.com/video.mp4",
            final_url="https://v9-default.365yg.com/final.mp4",
            source_mp4_access_mode="external_direct",
            file_purpose="user_data",
            filename="record-1.mp4",
            attempt_count=1,
            last_error="boom",
            updated_at="2026-04-13T00:00:00+00:00",
        )
    )

    assert _workflow(paths, Mp4FileUploadRunConfig(retry_failed=False))._pending_records() == []
    assert len(_workflow(paths, Mp4FileUploadRunConfig(retry_failed=True))._pending_records()) == 1


def test_workflow_downloads_uploads_and_cleans_temp_file(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_link("https://www.douyin.com/video/1"))
    monkeypatch.setenv("ARK_API_KEY", "test-key")

    uploaded = {}

    class FakeHttpResponse:
        status = 200
        headers = {"content-type": "video/mp4", "content-length": "24"}

        def __init__(self):
            self._chunks = [b"\x00\x00\x00\x18ftypmp42", b"video-bytes"]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def getcode(self):
            return self.status

        def read(self, _size: int):
            return self._chunks.pop(0) if self._chunks else b""

    def fake_urlopen(req, timeout):
        uploaded["download_url"] = req.full_url
        uploaded["timeout"] = timeout
        return FakeHttpResponse()

    class FakeFiles:
        def create(self, file, purpose):
            uploaded["purpose"] = purpose
            uploaded["file_bytes"] = file.read()
            return SimpleNamespace(id="file_ark_123")

    def fake_client_factory(base_url, api_key):
        uploaded["base_url"] = base_url
        uploaded["api_key"] = api_key
        return SimpleNamespace(files=FakeFiles())

    monkeypatch.setattr("search_agent.adapters.douyin.mp4_file_uploads.request.urlopen", fake_urlopen)

    summary = _workflow(paths, Mp4FileUploadRunConfig(batch_size=1), fake_client_factory).run()
    results = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).load_all()

    assert summary.processed_candidates == 1
    assert summary.successful_records == 1
    assert results[0].status == "success"
    assert results[0].file_id == "file_ark_123"
    assert results[0].sha256
    assert results[0].downloaded_bytes == len(uploaded["file_bytes"])
    assert uploaded["download_url"] == "https://v9-default.365yg.com/final.mp4"
    assert uploaded["purpose"] == "user_data"
    assert not list(paths.mp4_upload_tmp_dir.glob("*.mp4"))
    assert not list(paths.mp4_upload_tmp_dir.glob("*.part"))


def test_workflow_marks_non_video_download_failed(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_link("https://www.douyin.com/video/1"))
    monkeypatch.setenv("ARK_API_KEY", "test-key")

    class FakeHttpResponse:
        status = 200
        headers = {"content-type": "text/html", "content-length": "12"}

        def __init__(self):
            self._chunks = [b"<html></html>"]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def getcode(self):
            return self.status

        def read(self, _size: int):
            return self._chunks.pop(0) if self._chunks else b""

    monkeypatch.setattr("search_agent.adapters.douyin.mp4_file_uploads.request.urlopen", lambda *_args, **_kwargs: FakeHttpResponse())

    summary = _workflow(paths, Mp4FileUploadRunConfig(batch_size=1), lambda *_args: SimpleNamespace(files=None)).run()
    results = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).load_all()

    assert summary.successful_records == 0
    assert summary.skipped_items == 1
    assert results[0].status == "failed"
    assert "non-video" in (results[0].last_error or "")
    assert not list(paths.mp4_upload_tmp_dir.glob("*.part"))


def test_workflow_marks_missing_ark_key_failed_without_downloading(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.mp4_links_output, Mp4LinkRecord).append(_mp4_link("https://www.douyin.com/video/1"))
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.setattr("search_agent.adapters.douyin.mp4_file_uploads._load_dotenv_if_available", lambda: None)

    summary = _workflow(paths, Mp4FileUploadRunConfig(batch_size=1), lambda *_args: None).run()
    results = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).load_all()

    assert summary.processed_candidates == 1
    assert summary.skipped_items == 1
    assert results[0].status == "failed"
    assert "ARK_API_KEY" in (results[0].last_error or "")
