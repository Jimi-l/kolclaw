from __future__ import annotations

import logging
import time

from search_agent.artifacts import ArtifactManager
from search_agent.config import ContentAnalysisRunConfig, RuntimePaths
from search_agent.enums import AnalysisStatus, WorkflowStage
from search_agent.models.analysis import ContentAnalysisRecord, GeminiAnalysisPayload
from search_agent.models.common import RunSummary, TaggingContext
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.storage import ContentAnalysisQueueStore
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.tagging import GeminiContentAnalyzer, HeuristicTagger


class ContentAnalysisWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: ContentAnalysisRunConfig,
    ):
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.analysis")
        self.queue_store = ContentAnalysisQueueStore(self.paths.analysis_queue_output)
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.analysis_store = JsonlStore(self.paths.analysis_output, ContentAnalysisRecord)
        self.heuristic_tagger = HeuristicTagger()
        self.gemini_analyzer = GeminiContentAnalyzer(model_name=self.run_config.model_name)

    def run(self, priority_record_ids: set[str] | None = None) -> RunSummary:
        self.paths.ensure_directories()
        existing_results = self.analysis_store.load_all()
        processed_ids = {
            record.record_id
            for record in existing_results
            if getattr(record.analysis_status, "value", record.analysis_status)
            in {AnalysisStatus.COMPLETED.value, AnalysisStatus.FALLBACK.value}
        }
        pending = self.queue_store.load_pending(
            processed_record_ids=processed_ids,
            limit=self.run_config.max_items,
            priority_record_ids=priority_record_ids,
        )
        discovery_records = {record.record_id: record for record in self.discovery_store.load_all()}

        processed = completed = skipped = blocked = 0
        start_time = time.monotonic()

        for queued_record in pending:
            record = discovery_records.get(queued_record.record_id, queued_record)
            processed += 1
            try:
                payload = self.gemini_analyzer.analyze(record)
                analysis_record = self._build_analysis_record(
                    record,
                    payload,
                    status=AnalysisStatus.COMPLETED,
                    backend="gemini",
                    model_name=self.run_config.model_name,
                    error_text=None,
                )
                updated_record = self._apply_analysis_result(
                    record,
                    payload,
                    status=AnalysisStatus.COMPLETED,
                    backend="gemini",
                    model_name=self.run_config.model_name,
                    error_text=None,
                )
                completed += 1
            except Exception as exc:
                fallback_payload = self._build_fallback_payload(record, str(exc))
                analysis_record = self._build_analysis_record(
                    record,
                    fallback_payload,
                    status=AnalysisStatus.FALLBACK,
                    backend="heuristic",
                    model_name=self.run_config.model_name,
                    error_text=str(exc),
                )
                updated_record = self._apply_analysis_result(
                    record,
                    fallback_payload,
                    status=AnalysisStatus.FALLBACK,
                    backend="heuristic",
                    model_name=self.run_config.model_name,
                    error_text=str(exc),
                )
                skipped += 1
                self.logger.warning(
                    "gemini content analysis failed; heuristic fallback applied",
                    extra={
                        "record_id": record.record_id,
                        "creator_name": record.creator_name,
                        "error_text": str(exc),
                    },
                )

            self.analysis_store.upsert(analysis_record)
            self.discovery_store.upsert(updated_record)
            discovery_records[updated_record.record_id] = updated_record

        duration_minutes = round((time.monotonic() - start_time) / 60, 2)
        return RunSummary(
            stage=WorkflowStage.CONTENT_ANALYSIS,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=0,
            output_path=str(self.paths.analysis_output),
            queue_path=str(self.paths.analysis_queue_output),
        )

    def _build_fallback_payload(self, record: CreatorDiscoveryRecord, error_text: str) -> GeminiAnalysisPayload:
        tagging = self.heuristic_tagger.tag(self._build_tagging_context(record))
        summary = (
            record.video_title_text
            or record.expanded_description_text
            or record.video_description_raw
            or record.active_text_summary
            or "页面可见文本不足，已使用启发式规则生成 KolClaw 内容标签。"
        )
        return GeminiAnalysisPayload(
            video_content_summary=summary,
            content_taxonomy_path=tagging.content_taxonomy_path,
            content_leaf_tags=tagging.content_leaf_tags,
            profession_tags=tagging.profession_tags,
            interest_tags=tagging.interest_tags,
            life_tags=tagging.life_tags,
            appearance_relation_tags=tagging.appearance_relation_tags,
            monetization=tagging.monetization,
            cooperate_type=tagging.cooperate_type,
            content_analysis_reasoning=tagging.label_reasoning or f"Gemini 分析失败，已回退 heuristic。错误：{error_text}",
            safety_or_uncertainty_note="Gemini 不可用或返回异常，当前结论来自规则推断。",
        )

    @staticmethod
    def _build_analysis_record(
        record: CreatorDiscoveryRecord,
        payload: GeminiAnalysisPayload,
        status: AnalysisStatus,
        backend: str,
        model_name: str | None,
        error_text: str | None,
    ) -> ContentAnalysisRecord:
        return ContentAnalysisRecord(
            record_id=record.record_id,
            creator_name=record.creator_name,
            video_url=record.video_url,
            analysis_status=status,
            analysis_backend=backend,
            analysis_model=model_name,
            keyframe_paths=record.keyframe_paths,
            video_content_summary=payload.video_content_summary,
            content_taxonomy_path=payload.content_taxonomy_path,
            content_leaf_tags=payload.content_leaf_tags,
            profession_tags=payload.profession_tags,
            interest_tags=payload.interest_tags,
            life_tags=payload.life_tags,
            appearance_relation_tags=payload.appearance_relation_tags,
            monetization=payload.monetization,
            cooperate_type=payload.cooperate_type,
            content_analysis_reasoning=payload.content_analysis_reasoning,
            analysis_error=error_text,
        )

    @staticmethod
    def _apply_analysis_result(
        record: CreatorDiscoveryRecord,
        payload: GeminiAnalysisPayload,
        status: AnalysisStatus,
        backend: str,
        model_name: str | None,
        error_text: str | None,
    ) -> CreatorDiscoveryRecord:
        return record.model_copy(
            update={
                "analysis_status": status,
                "analysis_backend": backend,
                "analysis_model": model_name,
                "video_content_summary": payload.video_content_summary,
                "content_analysis_reasoning": payload.content_analysis_reasoning,
                "analysis_error": error_text,
                "content_taxonomy_path": payload.content_taxonomy_path,
                "content_leaf_tags": payload.content_leaf_tags,
                "profession_tags": payload.profession_tags,
                "interest_tags": payload.interest_tags,
                "life_tags": payload.life_tags,
                "appearance_relation_tags": payload.appearance_relation_tags,
                "monetization": payload.monetization,
                "cooperate_type": payload.cooperate_type,
            }
        )

    @staticmethod
    def _build_tagging_context(record: CreatorDiscoveryRecord) -> TaggingContext:
        return TaggingContext(
            creator_name=record.creator_name,
            profile_bio=record.profile_bio,
            follower_count_raw=record.follower_count_raw,
            total_liked_count_raw=record.total_liked_count_raw,
            recommendation_video_summary=record.active_text_summary,
            video_description_raw=record.video_description_raw,
            video_title_text=record.video_title_text,
            expanded_description_text=record.expanded_description_text,
            video_text_bundle=record.video_text_bundle,
            chapter_texts=record.chapter_texts,
            related_search_terms=record.related_search_terms,
            author_statement_texts=record.author_statement_texts,
            recent_videos_summary=record.recent_video_titles,
            visible_subtitle_segments=record.visible_subtitle_segments,
            top_comments=record.top_comments,
            visible_scenes=record.visible_scenes,
            speaking_style=record.speaking_style,
            video_duration_pattern=record.video_duration_pattern,
            ai_generated_flag=record.ai_generated_flag,
            extra_notes=record.notes,
        )
