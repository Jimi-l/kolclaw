from __future__ import annotations

from search_agent.artifacts import ArtifactManager
from search_agent.adapters.douyin.video_url_analysis import VideoUrlAnalysisWorkflow
from search_agent.config import RuntimePaths, VideoUrlAnalysisRunConfig
from search_agent.enums import AnalysisStatus, NextAction, RecordStatus, WorkflowStage
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.video_url_analysis import AudienceProfile, EmotionArc, VideoUrlAnalysisPayload
from search_agent.storage.jsonl_store import JsonlStore


def _record(
    record_id: str,
    video_url: str,
    creator_name: str = "创作者",
    share_count_raw: str | None = None,
    follower_count_raw: str | None = None,
    follower_count_normalized: int | None = None,
) -> CreatorDiscoveryRecord:
    return CreatorDiscoveryRecord(
        record_id=record_id,
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/10",
        video_url=video_url,
        creator_name=creator_name,
        share_count_raw=share_count_raw,
        follower_count_raw=follower_count_raw,
        follower_count_normalized=follower_count_normalized,
        duplicate_key=f"douyin::{creator_name}",
        next_action=NextAction.CONTINUE,
    )


def _payload(theme: str = "旅行") -> VideoUrlAnalysisPayload:
    return VideoUrlAnalysisPayload(
        video_access_status="metadata_only",
        theme=theme,
        protagonist="女生",
        scene="海边",
        core_action="转场拍摄",
        action_highlights=["转场快", "服装切换"],
        encountered_people=[],
        people_story_traits=[],
        visual_highlights=["海边", "高颜值"],
        tags=["旅行", "颜值"],
        retention_reasons=["前五秒颜值吸引"],
        interaction_reasons=["想转发给朋友"],
        opening_hook_analysis="前五秒直接给高颜值海边画面。",
        audience_emotion=EmotionArc(opening="好奇", middle="沉浸", ending="满足"),
        core_audience=AudienceProfile(
            age_bands=["18-24"],
            gender_skew="女性偏多",
            income_level="中等",
            city_tier_preference=["一线", "新一线"],
            region_preference=["华东"],
            reasoning="旅行和颜值内容更容易吸引年轻女性。",
        ),
        replicability="中",
        replicability_reasoning="场景可复制，但颜值与镜头感有门槛。",
        series_continuation_interest="如果继续同风格更新，粉丝仍会继续看。",
        analysis_reasoning="基于链接和元数据综合判断。",
    )


def test_video_url_analysis_dedupes_by_latest_video_url(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    discovery_store.append(_record("old", "https://www.douyin.com/video/1", creator_name="旧作者"))
    discovery_store.append(_record("new", "https://www.douyin.com/video/1", creator_name="新作者"))

    def fake_analyze(self, record: CreatorDiscoveryRecord) -> VideoUrlAnalysisPayload:
        assert record.record_id == "new"
        assert record.creator_name == "新作者"
        return _payload(theme="影视")

    monkeypatch.setattr(
        "search_agent.tagging.gemini_video_url.GeminiVideoUrlAnalyzer.analyze",
        fake_analyze,
    )

    workflow = VideoUrlAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.VIDEO_URL_ANALYSIS),
        run_config=VideoUrlAnalysisRunConfig(),
    )
    summary = workflow.run()
    assert summary.processed_candidates == 1

    results = JsonlStore(paths.video_url_analysis_output, __import__("search_agent.models.video_url_analysis", fromlist=["VideoUrlAnalysisRecord"]).VideoUrlAnalysisRecord).load_all()
    assert len(results) == 1
    assert results[0].record_id == "new"
    assert results[0].theme == "影视"


def test_video_url_analysis_applies_viral_rules(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    discovery_store.append(_record("a", "https://www.douyin.com/video/100", share_count_raw="12.1万", follower_count_raw="500万"))
    discovery_store.append(_record("b", "https://www.douyin.com/video/101", share_count_raw="1.1万", follower_count_raw="20万"))
    discovery_store.append(_record("c", "https://www.douyin.com/video/102", share_count_raw="1.1万", follower_count_raw="50万"))

    monkeypatch.setattr(
        "search_agent.tagging.gemini_video_url.GeminiVideoUrlAnalyzer.analyze",
        lambda self, record: _payload(),
    )

    workflow = VideoUrlAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.VIDEO_URL_ANALYSIS),
        run_config=VideoUrlAnalysisRunConfig(),
    )
    workflow.run()
    from search_agent.models.video_url_analysis import VideoUrlAnalysisRecord

    results = {
        record.video_url: record
        for record in JsonlStore(paths.video_url_analysis_output, VideoUrlAnalysisRecord).load_all()
    }
    assert results["https://www.douyin.com/video/100"].is_viral is True
    assert results["https://www.douyin.com/video/100"].viral_rule_hit == "share_gt_100k"
    assert results["https://www.douyin.com/video/101"].is_viral is True
    assert results["https://www.douyin.com/video/101"].viral_rule_hit == "share_gt_10k_and_followers_lt_300k"
    assert results["https://www.douyin.com/video/102"].is_viral is False
    assert results["https://www.douyin.com/video/102"].viral_rule_hit == "no_rule_hit"


def test_video_url_analysis_upserts_by_video_url_and_records_failure(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    discovery_store = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord)
    discovery_store.append(_record("ok", "https://www.douyin.com/video/201"))

    def fail(self, record: CreatorDiscoveryRecord) -> VideoUrlAnalysisPayload:
        raise RuntimeError("upstream failed")

    monkeypatch.setattr(
        "search_agent.tagging.gemini_video_url.GeminiVideoUrlAnalyzer.analyze",
        fail,
    )

    workflow = VideoUrlAnalysisWorkflow(
        paths=paths,
        artifacts=ArtifactManager.create(paths.artifacts_dir, WorkflowStage.VIDEO_URL_ANALYSIS),
        run_config=VideoUrlAnalysisRunConfig(force=True),
    )
    workflow.run()
    from search_agent.models.video_url_analysis import VideoUrlAnalysisRecord

    records = JsonlStore(paths.video_url_analysis_output, VideoUrlAnalysisRecord).load_all()
    assert len(records) == 1
    assert records[0].analysis_status == AnalysisStatus.FAILED.value
    assert records[0].analysis_error == "upstream failed"
