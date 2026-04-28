from __future__ import annotations

from search_agent.adapters.douyin.doubao_video_analysis import (
    DoubaoVideoAnalysisResult,
    DoubaoVideoAnalysisWorkflow,
    build_doubao_video_prompt,
)
from search_agent.artifacts import ArtifactManager
from search_agent.config import DoubaoVideoAnalysisRunConfig, RuntimePaths
from search_agent.enums import NextAction, RecordStatus, WorkflowStage
from search_agent.models.common import CommentSnippet
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.storage.jsonl_store import JsonlStore


def _upload(video_url: str, status: str = "success", file_id: str | None = "file_123", record_id: str = "record-1"):
    return Mp4FileUploadRecord(
        record_id=record_id,
        video_url=video_url,
        creator_name="创作者",
        status=status,  # type: ignore[arg-type]
        direct_mp4_url="https://v9-default.365yg.com/video.mp4",
        final_url="https://v9-default.365yg.com/final.mp4",
        source_mp4_access_mode="external_direct",
        file_id=file_id,
        file_purpose="user_data",
        filename=f"{record_id}.mp4",
        content_type="video/mp4",
        content_length="2048",
        downloaded_bytes=2048,
        sha256="abc",
        attempt_count=1,
        last_error=None,
        updated_at="2026-04-13T00:00:00+00:00",
    )


def _discovery(video_url: str) -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id="record-1",
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/13",
        video_url=video_url,
        creator_name="创作者",
        follower_count_raw="20万",
        like_count_raw="18.0万",
        comment_count_raw="1.0万",
        favorite_count_raw="1.3万",
        share_count_raw="4.2万",
        video_title_text="测试标题",
        video_description_raw="测试简介",
        visible_subtitle_segments=["字幕一", "字幕二"],
        top_comments=[
            CommentSnippet(author_name="用户A", text="太有代入感了", like_count_raw="100", source="network"),
        ],
        duplicate_key="douyin::创作者",
        next_action=NextAction.CONTINUE,
    )


def _workflow(paths: RuntimePaths, run_config: DoubaoVideoAnalysisRunConfig | None = None, analyzer_factory=None):
    return DoubaoVideoAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS),
        run_config=run_config or DoubaoVideoAnalysisRunConfig(batch_size=10),
        client_factory=lambda *_args: object(),
        analyzer_factory=analyzer_factory,
    )


def test_pending_records_only_uses_success_uploads_with_file_id(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    upload_store = JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord)
    upload_store.append(_upload("https://www.douyin.com/video/1", record_id="ok"))
    upload_store.append(_upload("https://www.douyin.com/video/2", file_id=None, record_id="missing-file"))
    upload_store.append(_upload("https://www.douyin.com/video/3", status="failed", record_id="failed"))

    pending = _workflow(paths)._pending_records()

    assert [record.record_id for record in pending] == ["ok"]


def test_pending_records_skips_completed_and_retries_failed_when_enabled(tmp_path) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    video_url = "https://www.douyin.com/video/1"
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(_upload(video_url))
    JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).append(
        DoubaoVideoAnalysisRecord(
            record_id="record-1",
            video_url=video_url,
            creator_name="创作者",
            file_id="file_123",
            status="failed",
            analysis_model="doubao-seed-2-0-lite-260215",
            attempt_count=1,
            last_error="boom",
            updated_at="2026-04-13T00:00:00+00:00",
        )
    )

    assert _workflow(paths, DoubaoVideoAnalysisRunConfig(retry_failed=False))._pending_records() == []
    assert len(_workflow(paths, DoubaoVideoAnalysisRunConfig(retry_failed=True))._pending_records()) == 1


def test_prompt_includes_file_context_discovery_fields_and_fixed_rule() -> None:
    upload = _upload("https://www.douyin.com/video/1")
    prompt = build_doubao_video_prompt(upload, _discovery(upload.video_url))

    assert "file_id: file_123" in prompt
    assert "转发量 > 10万，则一定是爆款" in prompt
    assert "转发量 > 1万，并且账号粉丝 < 30万" in prompt
    assert "点赞=18.0万 评论=1.0万 收藏=1.3万 转发=4.2万" in prompt
    assert "测试标题" in prompt
    assert "字幕一" in prompt
    assert "用户A: 太有代入感了" in prompt


def test_workflow_writes_completed_analysis(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    video_url = "https://www.douyin.com/video/1"
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(_upload(video_url))
    JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).append(_discovery(video_url))
    monkeypatch.setenv("ARK_API_KEY", "test-key")

    class FakeAnalyzer:
        def analyze(self, upload, discovery):
            assert upload.file_id == "file_123"
            assert discovery.creator_name == "创作者"
            return DoubaoVideoAnalysisResult(
                payload={
                    "is_viral": True,
                    "viral_rule_hit": "share_gt_10k_and_followers_lt_300k",
                    "viral_rule_reasoning": "转发过万且粉丝低于30万。",
                    "theme": "街头故事",
                    "protagonist": "年轻女性",
                    "scene": "街头",
                    "core_action": "互动",
                    "story_traits": ["反差"],
                    "visual_hooks": ["前五秒出现冲突"],
                    "replicability": "中",
                    "replicability_reasoning": "场景可复制，人物条件部分依赖。",
                    "tags": ["vlog"],
                    "retention_reasons": ["悬念"],
                    "interaction_reasons": ["评论表达共鸣"],
                    "opening_hook_analysis": "开头有钩子。",
                    "audience_emotion": {"opening": "好奇", "middle": "代入", "ending": "共鸣"},
                    "core_audience": {"age": "18-30"},
                    "series_continuation_interest": "可以延续。",
                    "analysis_reasoning": "综合视频和互动数据判断。",
                },
                raw_response_text='{"is_viral": true}',
                response_id="resp_123",
            )

    summary = _workflow(paths, DoubaoVideoAnalysisRunConfig(batch_size=1), lambda *_args: FakeAnalyzer()).run()
    results = JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).load_all()

    assert summary.processed_candidates == 1
    assert summary.successful_records == 1
    assert results[0].status == "completed"
    assert results[0].response_id == "resp_123"
    assert results[0].is_viral is True
    assert results[0].theme == "街头故事"
    assert results[0].tags == ["vlog"]


def test_analyzer_sends_video_file_id_without_filename() -> None:
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return {"id": "resp_123", "output_text": '{"is_viral": true, "viral_rule_hit": "rule", "viral_rule_reasoning": "reason", "theme": "theme", "protagonist": "p", "scene": "s", "core_action": "a", "story_traits": [], "visual_hooks": [], "replicability": "中", "replicability_reasoning": "r", "tags": [], "retention_reasons": [], "interaction_reasons": [], "opening_hook_analysis": "o", "audience_emotion": {}, "core_audience": {}, "series_continuation_interest": "i", "analysis_reasoning": "ar"}'}

    from search_agent.adapters.douyin.doubao_video_analysis import DoubaoVideoAnalyzer

    analyzer = DoubaoVideoAnalyzer(client=type("FakeClient", (), {"responses": FakeResponses()})(), model_name="model")
    analyzer.analyze(_upload("https://www.douyin.com/video/1"), None)

    file_part = calls[0]["input"][0]["content"][0]
    assert file_part == {"type": "input_video", "file_id": "file_123"}


def test_workflow_marks_invalid_model_output_failed(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(_upload("https://www.douyin.com/video/1"))
    monkeypatch.setenv("ARK_API_KEY", "test-key")

    class FakeAnalyzer:
        def analyze(self, upload, discovery):
            raise RuntimeError("Doubao response does not contain a JSON object")

    summary = _workflow(paths, DoubaoVideoAnalysisRunConfig(batch_size=1), lambda *_args: FakeAnalyzer()).run()
    results = JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).load_all()

    assert summary.successful_records == 0
    assert summary.skipped_items == 1
    assert results[0].status == "failed"
    assert "JSON object" in (results[0].last_error or "")


def test_workflow_marks_missing_ark_key_failed_without_client(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    JsonlStore(paths.mp4_file_uploads_output, Mp4FileUploadRecord).append(_upload("https://www.douyin.com/video/1"))
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.setattr("search_agent.adapters.douyin.doubao_video_analysis._load_dotenv_if_available", lambda: None)

    summary = _workflow(paths, DoubaoVideoAnalysisRunConfig(batch_size=1), lambda *_args: None).run()
    results = JsonlStore(paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord).load_all()

    assert summary.processed_candidates == 1
    assert summary.skipped_items == 1
    assert results[0].status == "failed"
    assert "ARK_API_KEY" in (results[0].last_error or "")
