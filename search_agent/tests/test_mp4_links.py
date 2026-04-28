from __future__ import annotations

from search_agent.adapters.douyin.mp4_links import DouyinMp4LinkWorkflow
from search_agent.adapters.douyin.mp4_resolver import BrowserContextOnlyMp4Error, Mp4ResolveResult, extract_mp4_candidates, select_best_candidate
from search_agent.artifacts import ArtifactManager
from search_agent.config import BrowserConfig, Mp4LinkRunConfig, RuntimePaths
from search_agent.enums import NextAction, RecordStatus, WorkflowStage
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


def _record(record_id: str, video_url: str, creator_name: str = "创作者") -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=record_id,
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/10",
        video_url=video_url,
        creator_name=creator_name,
        duplicate_key=f"douyin::{creator_name}",
        next_action=NextAction.CONTINUE,
    )


def _mp4_record(video_url: str, status: str = "success", record_id: str = "existing") -> Mp4LinkRecord:
    return Mp4LinkRecord(
        record_id=record_id,
        video_url=video_url,
        creator_name="已有作者",
        status=status,  # type: ignore[arg-type]
        direct_mp4_url="https://v26-web.douyinvod.com/video.mp4" if status == "success" else None,
        source="play_addr" if status == "success" else None,
        content_type="video/mp4" if status == "success" else None,
        content_length="1000" if status == "success" else None,
        attempt_count=1,
        last_error=None if status == "success" else "boom",
        updated_at="2026-04-13T00:00:00+00:00",
    )


def _workflow(paths: RuntimePaths, run_config: Mp4LinkRunConfig | None = None) -> DouyinMp4LinkWorkflow:
    return DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin", headless=True),
        run_config=run_config or Mp4LinkRunConfig(batch_size=10),
    )


def test_pending_records_skips_success_and_keeps_ten_unresolved(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    mp4_store = JsonlStore(paths.mp4_links_output, Mp4LinkRecord)

    urls = [f"https://www.douyin.com/video/{7600000000000000000 + index}" for index in range(12)]
    for index, url in enumerate(urls):
        discovery_store.append(_record(f"record-{index}", url))
    mp4_store.append(_mp4_record(urls[0], record_id="record-0"))
    mp4_store.append(_mp4_record(urls[1], record_id="record-1"))

    pending = _workflow(paths)._pending_records()

    assert len(pending) == 10
    assert {record.video_url for record in pending}.isdisjoint({urls[0], urls[1]})


def test_pending_records_dedupes_by_latest_discovery_record(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    video_url = "https://www.douyin.com/video/7612345678901234567"
    discovery_store.append(_record("old", video_url, creator_name="旧作者"))
    discovery_store.append(_record("new", video_url, creator_name="新作者"))

    pending = _workflow(paths)._pending_records()

    assert len(pending) == 1
    assert pending[0].record_id == "new"
    assert pending[0].creator_name == "新作者"


def test_pending_records_retries_failed_only_when_enabled(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    mp4_store = JsonlStore(paths.mp4_links_output, Mp4LinkRecord)
    video_url = "https://www.douyin.com/video/7612345678901234567"
    discovery_store.append(_record("failed", video_url))
    mp4_store.append(_mp4_record(video_url, status="failed", record_id="failed"))

    assert _workflow(paths, Mp4LinkRunConfig(retry_failed=False))._pending_records() == []
    assert len(_workflow(paths, Mp4LinkRunConfig(retry_failed=True))._pending_records()) == 1


def test_extract_mp4_candidates_prefers_video_mp4_cdn_over_media_response() -> None:
    payload = {
        "aweme_list": [
            {
                "aweme_id": "7699999999999999999",
                "video": {
                    "play_addr": {
                        "width": 1080,
                        "height": 1920,
                        "data_size": 9999999,
                        "url_list": [
                            "https://v26-web.douyinvod.com/wrong/video/tos/cn/?mime_type=video_mp4&dy_q=1",
                        ],
                    },
                },
            },
            {
                "aweme_id": "7612345678901234567",
                "video": {
                    "play_addr": {
                        "width": 720,
                        "height": 1280,
                        "data_size": 1069132,
                        "url_list": [
                            "https://www.douyin.com/aweme/v1/play/?video_id=v0300&is_play_url=1",
                            "https://v26-web.douyinvod.com/path/video/tos/cn/?mime_type=video_mp4&dy_q=1",
                            "https://v9-default.365yg.com/hash/video/tos/cn/tos-cn-v-0015c000-ce/demo/?a=0&lr=unwatermarked&br=12492&bt=12492&mime_type=video_mp4",
                        ],
                    },
                    "download_addr": {
                        "width": 720,
                        "height": 1280,
                        "data_size": 2069132,
                        "url_list": [
                            "https://v9-default.365yg.com/download/video/tos/cn/tos-cn-v-0015c000-ce/demo/?a=0&lr=unwatermarked&br=22492&bt=22492&mime_type=video_mp4",
                        ],
                    },
                    "cover": {
                        "url_list": [
                            "https://p3-pc-sign.douyinpic.com/cover.jpeg?x-signature=abc",
                        ]
                    },
                },
            },
        ]
    }

    candidates = extract_mp4_candidates(payload, target_video_id="7612345678901234567")
    selected = select_best_candidate(candidates)

    assert len(candidates) == 4
    assert selected is not None
    assert "365yg.com" in selected.url
    assert "lr=unwatermarked" in selected.url
    assert selected.source == "download_addr"
    assert "mime_type=video_mp4" in selected.url


def test_extract_mp4_candidates_supports_bit_rate_and_ignores_static_assets() -> None:
    payload = {
        "aweme_detail": {
            "aweme_id": "7612345678901234567",
            "video": {
                "play_addr": {
                    "url_list": [
                        "https://lf-douyin-pc-web.douyinstatic.com/obj/douyin-pc-web/ies/douyin_web/player.css",
                    ]
                },
                "bit_rate": [
                    {
                        "play_addr": {
                            "width": 1080,
                            "height": 1920,
                            "data_size": 4096,
                            "url_list": [
                                "https://v11-default.365yg.com/hash/video/tos/cn/path/?a=0&lr=unwatermarked&mime_type=video_mp4",
                            ],
                        }
                    }
                ],
            },
        }
    }

    candidates = extract_mp4_candidates(payload, target_video_id="7612345678901234567")

    assert len(candidates) == 1
    assert candidates[0].source == "play_addr"
    assert "365yg.com" in candidates[0].url


def test_workflow_processes_batch_and_writes_success(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    for index in range(10):
        discovery_store.append(_record(f"record-{index}", f"https://www.douyin.com/video/{7600000000000000000 + index}"))

    class FakeBrowserSession:
        def __init__(self, *_args, **_kwargs):
            self.page = object()
            self.context = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeResolver:
        def __init__(self, *_args, **_kwargs):
            pass

        def resolve(self, record: CreatorDiscoveryRecord) -> Mp4ResolveResult:
            return Mp4ResolveResult(
                direct_mp4_url=f"https://v26-web.douyinvod.com/{record.record_id}.mp4",
                source="play_addr",
                access_mode="external_direct",
                final_url=f"https://v26-web.douyinvod.com/{record.record_id}.mp4",
                content_type="video/mp4",
                content_length="2048",
                probe_status_code=206,
                probe_content_range="bytes 0-2047/4096",
            )

    monkeypatch.setattr("search_agent.adapters.douyin.mp4_links.BrowserSession", FakeBrowserSession)
    workflow = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin", headless=True),
        run_config=Mp4LinkRunConfig(batch_size=10),
        resolver_factory=FakeResolver,
    )

    summary = workflow.run()
    results = JsonlStore(paths.mp4_links_output, Mp4LinkRecord).load_all()

    assert summary.processed_candidates == 10
    assert summary.successful_records == 10
    assert len(results) == 10
    assert all(record.status == "success" for record in results)
    assert all(record.access_mode == "external_direct" for record in results)


def test_workflow_marks_browser_context_only_as_failed(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).append(
        _record("record-1", "https://www.douyin.com/video/7612345678901234567")
    )

    class FakeBrowserSession:
        def __init__(self, *_args, **_kwargs):
            self.page = object()
            self.context = object()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeResolver:
        def __init__(self, *_args, **_kwargs):
            pass

        def resolve(self, record: CreatorDiscoveryRecord) -> Mp4ResolveResult:
            result = Mp4ResolveResult(
                direct_mp4_url="https://v26-web.douyinvod.com/context-only.mp4",
                source="media_response",
                access_mode="browser_context_only",
                final_url="https://v26-web.douyinvod.com/context-only.mp4",
                content_type="video/mp4",
                content_length="2048",
                probe_status_code=206,
                probe_content_range="bytes 0-2047/4096",
            )
            raise BrowserContextOnlyMp4Error(result, "browser context only")

    monkeypatch.setattr("search_agent.adapters.douyin.mp4_links.BrowserSession", FakeBrowserSession)
    workflow = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS),
        browser_config=BrowserConfig(site_name="douyin", headless=True),
        run_config=Mp4LinkRunConfig(batch_size=1),
        resolver_factory=FakeResolver,
    )

    summary = workflow.run()
    results = JsonlStore(paths.mp4_links_output, Mp4LinkRecord).load_all()

    assert summary.processed_candidates == 1
    assert summary.successful_records == 0
    assert summary.skipped_items == 1
    assert results[0].status == "failed"
    assert results[0].access_mode == "browser_context_only"
    assert results[0].direct_mp4_url == "https://v26-web.douyinvod.com/context-only.mp4"
