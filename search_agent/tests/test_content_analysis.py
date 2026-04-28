from __future__ import annotations

from search_agent.adapters.douyin.content_analysis import ContentAnalysisWorkflow
from search_agent.adapters.douyin.page import (
    _build_comment_collection_result,
    _build_video_text_bundle,
    _clean_video_description_text,
    _extract_author_statement_texts,
    _extract_aweme_items,
    _extract_chapter_texts,
    _extract_comment_threads,
    _extract_related_search_terms,
    _extract_video_id_from_url,
    _extract_video_title_text,
    _merge_comment_snippets,
    _merge_subtitle_segments,
    _sanitize_creator_name,
)
from search_agent.artifacts import ArtifactManager
from search_agent.config import ContentAnalysisRunConfig, RuntimePaths
from search_agent.enums import AnalysisStatus, NextAction, RecordStatus, WorkflowStage
from search_agent.models.common import CommentSnippet, TaggingContext
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.storage.queue import ContentAnalysisQueueStore
from search_agent.tagging import HeuristicTagger


def test_clean_video_description_text_removes_feed_chrome_noise() -> None:
    text = """
    00:04 / 40:59
    登录后可发布弹幕
    发送
    倍速
    智能
    清屏
    连播
    登录后分享给朋友 。。。 一键登录 登录即同意用户协议和隐私政策 登录其他账号 复制链接
    @沟渠 · 6天前 精彩解读正午阳光力作《命悬一生》吴细妹的悲惨一生！ #影视经典补完计划
    相关搜索： 悬疑电影
    """
    cleaned = _clean_video_description_text(text)
    assert cleaned is not None
    assert "命悬一生" in cleaned
    assert "登录后分享给朋友" not in cleaned
    assert "一键登录" not in cleaned
    assert "复制链接" not in cleaned


def test_clean_video_description_text_strips_metric_prefix_and_side_panel_noise() -> None:
    text = """
    9.1万 1943 1.2万 3.2万 听抖音
    详情 TA的作品 评论 问AI 相关推荐
    @小薯条 · 6天前 你的心 可以回到第一次见我那么真吗 #走拍
    全部评论(1943)
    """
    cleaned = _clean_video_description_text(text)
    assert cleaned == "@小薯条 · 6天前 你的心 可以回到第一次见我那么真吗 #走拍"


def test_extract_metadata_helpers_from_video_text() -> None:
    text = "@老酱电影 · 2月28日 第1章：引言 一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说 相关搜索： 悬疑电影 作者声明：内容来源于网络"
    assert _extract_video_title_text(text) == "第1章：引言 一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说"
    assert _extract_chapter_texts(text) == ["第1章：引言"]
    assert _extract_related_search_terms(text) == ["悬疑电影"]
    assert _extract_author_statement_texts(text) == ["作者声明：内容来源于网络", "内容来源于网络"]


def test_build_video_text_bundle_dedupes_redundant_description_sections() -> None:
    bundle = _build_video_text_bundle(
        title_text="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
        description_text="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
        expanded_description_text="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
        chapter_texts=["第1章：引言"],
        related_search_terms=["悬疑电影"],
        author_statement_texts=[],
        visible_subtitle_segments=[],
        top_comments=[],
    )
    assert bundle == "简介：一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说；章节：第1章：引言；相关搜索：悬疑电影"


def test_merge_subtitle_segments_dedupes_and_caps() -> None:
    merged = _merge_subtitle_segments(["第一句", "第二句"], ["第二句", "第三句", "第四句", "第五句", "第六句", "第七句"])
    assert merged == ["第一句", "第二句", "第三句", "第四句", "第五句", "第六句"]


def test_extract_aweme_items_and_comment_threads_from_network_payload() -> None:
    payload = {
        "aweme_list": [
            {
                "aweme_id": "7612345678901234567",
                "desc": "这是视频介绍 #测试",
                "author": {"nickname": "示例达人", "sec_uid": "MS4wLjABAAAA-test"},
            }
        ],
        "comments": [
            {
                "text": "这个视频讲得真清楚",
                "digg_count": 123,
                "user": {"nickname": "评论用户A"},
            },
            {
                "text": "收藏了，回头慢慢看",
                "digg_count": 45,
                "user": {"nickname": "评论用户B"},
            },
        ],
        "aweme_id": "7612345678901234567",
    }

    aweme_items = _extract_aweme_items(payload)
    assert aweme_items[0]["video_url"] == "https://www.douyin.com/video/7612345678901234567"
    assert aweme_items[0]["creator_name"] == "示例达人"
    assert aweme_items[0]["creator_profile_url"] == "https://www.douyin.com/user/MS4wLjABAAAA-test"

    comment_threads = _extract_comment_threads(payload)
    assert comment_threads[0][0] == "7612345678901234567"
    assert comment_threads[0][1][0].text == "这个视频讲得真清楚"
    assert comment_threads[0][1][0].source == "network"


def test_extract_comment_threads_supports_nested_payload_and_url_fallback() -> None:
    nested_payload = {
        "data": {
            "cursor": 0,
            "has_more": 1,
            "comments": [
                {
                    "text": "第一条嵌套评论",
                    "digg_count": 8,
                    "user": {"nickname": "嵌套用户"},
                }
            ],
        }
    }
    nested_threads = _extract_comment_threads(nested_payload, fallback_video_id="7611111111111111111")
    assert nested_threads == [
        (
            "7611111111111111111",
            [CommentSnippet(author_name="嵌套用户", text="第一条嵌套评论", like_count_raw="8", source="network")],
        )
    ]

    aweme_payload = {
        "comment_info": {
            "aweme_id": "7622222222222222222",
            "comments": [
                {
                    "text": "第二条评论",
                    "digg_count": 3,
                    "user": {"nickname": "评论用户C"},
                }
            ],
        }
    }
    aweme_threads = _extract_comment_threads(aweme_payload)
    assert aweme_threads[0][0] == "7622222222222222222"
    assert aweme_threads[0][1][0].text == "第二条评论"


def test_merge_comment_snippets_prefers_unique_text_and_limits() -> None:
    network = [
        CommentSnippet(author_name="A", text="这条评论很有用", like_count_raw="12", source="network"),
        CommentSnippet(author_name="B", text="第二条评论", like_count_raw="3", source="network"),
    ]
    ui = [
        CommentSnippet(author_name="C", text="这条评论很有用", like_count_raw="8", source="ui"),
        CommentSnippet(author_name="D", text="第三条评论", like_count_raw="1", source="ui"),
    ]

    merged = _merge_comment_snippets(network, ui)
    assert [comment.text for comment in merged] == ["这条评论很有用", "第二条评论", "第三条评论"]


def test_build_comment_collection_result_tracks_source_and_failure_status() -> None:
    network = [CommentSnippet(author_name="A", text="网络评论", like_count_raw="12", source="network")]
    ui = [CommentSnippet(author_name="B", text="界面评论", like_count_raw="6", source="ui")]
    success = _build_comment_collection_result(
        network_comments=network,
        ui_comments=ui,
        triggered=True,
        panel_visible=True,
        parse_failed=False,
        network_url="https://www.douyin.com/aweme/v1/web/comment/list/?aweme_id=1",
    )
    assert success.source == "mixed"
    assert success.status == "success"
    assert len(success.comments) == 2

    parse_failed = _build_comment_collection_result(
        network_comments=[],
        ui_comments=[],
        triggered=True,
        panel_visible=True,
        parse_failed=True,
        network_url=None,
    )
    assert parse_failed.status == "parse_failed"

    panel_empty = _build_comment_collection_result(
        network_comments=[],
        ui_comments=[],
        triggered=True,
        panel_visible=True,
        parse_failed=False,
        network_url=None,
    )
    assert panel_empty.status == "panel_empty"

    network_miss = _build_comment_collection_result(
        network_comments=[],
        ui_comments=[],
        triggered=True,
        panel_visible=False,
        parse_failed=False,
        network_url=None,
    )
    assert network_miss.status == "network_miss"


def test_extract_video_id_from_url_supports_standard_video_path() -> None:
    assert _extract_video_id_from_url("https://www.douyin.com/video/7612345678901234567?previous=1") == "7612345678901234567"


def test_sanitize_creator_name_rejects_time_progress_text() -> None:
    assert _sanitize_creator_name("00:05 / 00:32") is None


def test_heuristic_tagger_maps_film_explainer_to_kolclaw_taxonomy() -> None:
    tagger = HeuristicTagger()
    result = tagger.tag(
        TaggingContext(
            creator_name="老酱电影",
            recommendation_video_summary="00:03 / 27:35 @老酱电影 · 2月28日 一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说 相关搜索： 悬疑电影",
            video_title_text="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
            video_description_raw="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
            expanded_description_text="一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说",
            related_search_terms=["悬疑电影"],
            video_text_bundle="标题：一个天才运用数学知识，竟制造了一场无人能解的完美犯罪！ #电影解说；相关搜索：悬疑电影",
        )
    )
    assert result.content_taxonomy_path[:2] == ["影视娱乐", "影视综"]
    assert result.content_leaf_tags == ["影视解说"]
    assert result.monetization == []
    assert result.cooperate_type == "60s+"


def test_heuristic_tagger_does_not_overinfer_ai_from_warning_banner() -> None:
    tagger = HeuristicTagger()
    result = tagger.tag(
        TaggingContext(
            creator_name="淡然",
            recommendation_video_summary="00:02 / 00:10 @淡然 · 1周前 他们说我是冷白皮肤 #守店日常 疑似使用了 AI 生成技术，请谨慎甄别",
            video_title_text="他们说我是冷白皮肤 #守店日常",
            video_description_raw="他们说我是冷白皮肤 #守店日常 疑似使用了 AI 生成技术，请谨慎甄别",
            author_statement_texts=["疑似使用了 AI 生成技术，请谨慎甄别"],
        )
    )
    assert result.profession_tags == []
    assert result.interest_tags == []
    assert result.content_taxonomy_path != ["3C 数码科技", "科技互联网", "AIGC,AI 整活", "AI 应用"]


def test_content_analysis_workflow_falls_back_to_heuristic(tmp_path, monkeypatch) -> None:
    paths = RuntimePaths.defaults(project_root=tmp_path)
    paths.ensure_directories()
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.CONTENT_ANALYSIS)

    record = CreatorDiscoveryRecord(
        record_id="dy_test_record",
        status=RecordStatus.DISCOVERED,
        collection_date="2026/04/08",
        video_url="https://www.douyin.com/video/7612345678901234567",
        video_url_capture_source="network",
        creator_name="示例达人",
        follower_count_raw="12.5万",
        total_liked_count_raw="58.4万",
        profile_bio="一个讲电影和剧情解说的账号",
        active_text_summary="第1集：《纸牌屋》深度解析 第一期 00:03 / 16:20",
        video_title_text="第1集：《纸牌屋》深度解析 第一期",
        video_description_raw="第1集：《纸牌屋》深度解析 第一期 #纸牌屋 #美剧",
        expanded_description_text="第1集：《纸牌屋》深度解析 第一期 #纸牌屋 #美剧",
        video_text_bundle="标题：第1集：《纸牌屋》深度解析 第一期；简介：#纸牌屋 #美剧",
        chapter_texts=["第1集：纸牌屋"],
        related_search_terms=["纸牌屋"],
        author_statement_texts=[],
        visible_subtitle_segments=["从看门狗到狩猎者", "弗兰克开始黑化"],
        top_comments=[CommentSnippet(author_name="路人甲", text="讲得很细", like_count_raw="88", source="network")],
        top_comments_source="network",
        comment_collection_status="success",
        comment_collection_debug="comment_api=https://www.douyin.com/comment/list?aweme_id=7612345678901234567",
        keyframe_paths=[],
        total_interaction_text="👍24.9万 💬1667 ↗️1.5万 ⭐7.6万",
        content_taxonomy_path=[],
        content_leaf_tags=[],
        profession_tags=[],
        interest_tags=[],
        life_tags=[],
        appearance_relation_tags=[],
        monetization=[],
        duplicate_key="douyin::示例达人",
        next_action=NextAction.CONTINUE,
        analysis_status=AnalysisStatus.PENDING,
        analysis_backend="pending",
        analysis_model="gemini-2.5-flash",
    )

    JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).append(record)
    ContentAnalysisQueueStore(paths.analysis_queue_output).enqueue(record)

    workflow = ContentAnalysisWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=ContentAnalysisRunConfig(
            enabled=True,
            max_items=5,
            keyframe_count=4,
            model_name="gemini-2.5-flash",
        ),
    )

    def boom(_record: CreatorDiscoveryRecord):
        raise RuntimeError("boom")

    monkeypatch.setattr(workflow.gemini_analyzer, "analyze", boom)

    summary = workflow.run(priority_record_ids={record.record_id})
    assert summary.processed_candidates == 1

    updated_records = JsonlStore(paths.discovery_output, CreatorDiscoveryRecord).load_all()
    assert len(updated_records) == 1
    assert getattr(updated_records[0].analysis_status, "value", updated_records[0].analysis_status) == AnalysisStatus.FALLBACK.value
    assert updated_records[0].analysis_backend == "heuristic"
    assert updated_records[0].analysis_error == "boom"
    assert updated_records[0].video_content_summary is not None
    assert updated_records[0].content_taxonomy_path[:2] == ["影视娱乐", "影视综"]
