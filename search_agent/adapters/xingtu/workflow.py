from __future__ import annotations

import logging
import random
import time

from search_agent.artifacts import ArtifactManager
from search_agent.browser.session import BrowserSession
from search_agent.config import BrowserConfig, EnrichmentRunConfig, RuntimePaths
from search_agent.enums import MatchConfidence, NextAction, RecordStatus, WorkflowStage
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.enrichment import XingtuEnrichmentRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.storage.queue import XingtuQueueStore
from search_agent.utils.matching import evaluate_xingtu_match

from .page import XingtuPageAdapter, XingtuSearchOutcome


class XingtuEnrichmentWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        browser_config: BrowserConfig,
        run_config: EnrichmentRunConfig,
    ):
        self.paths = paths
        self.artifacts = artifacts
        self.browser_config = browser_config
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.xingtu")
        self.queue_store = XingtuQueueStore(self.paths.queue_output)
        self.enrichment_store = JsonlStore(self.paths.enrichment_output, XingtuEnrichmentRecord)

    def run(self) -> RunSummary:
        self.paths.ensure_directories()
        existing_results = self.enrichment_store.load_all()
        processed_ids = {record.record_id for record in existing_results}
        queued_records = self.queue_store.load_pending(processed_record_ids=processed_ids, limit=self.run_config.max_items)

        processed = completed = skipped = blocked = 0
        start_time = time.monotonic()

        with BrowserSession(self.browser_config, self.paths.browser_state_dir / "xingtu") as browser:
            adapter = XingtuPageAdapter(browser.page, self.artifacts, self.logger)
            adapter.open_homepage()

            for record in queued_records:
                processed += 1
                self._sleep_between_queries(browser.page)
                try:
                    outcome = self._search_with_fallback(adapter, record)
                    enrichment_record = self._build_from_search_outcome(record, outcome)
                    if enrichment_record is not None:
                        self.enrichment_store.append(enrichment_record)
                        if enrichment_record.enrichment_status == RecordStatus.BLOCKED:
                            blocked += 1
                        else:
                            skipped += 1
                        continue

                    best_candidate, best_match = self._choose_best_candidate(record, outcome)
                    if best_candidate is None or best_match is None:
                        ambiguous = XingtuEnrichmentRecord(
                            record_id=record.record_id,
                            creator_name=record.creator_name or "unknown",
                            status=record.status,
                            search_name_used=outcome.query,
                            match_confidence=MatchConfidence.LOW,
                            match_reason="搜索结果存在同名歧义，无法稳定确认同一达人",
                            field_missing_list=["xingtu_id", "xingtu_profile_url", "price_20s", "price_20_60s", "price_60s_plus"],
                            enrichment_status=RecordStatus.AMBIGUOUS_MATCH,
                            next_action=NextAction.MANUAL_REVIEW,
                        )
                        self.enrichment_store.append(ambiguous)
                        skipped += 1
                        continue

                    adapter.open_candidate(best_candidate)
                    detail = adapter.extract_details(record.creator_name or "creator")
                    field_missing = sorted(set(detail.field_missing_list))
                    status = RecordStatus.FIELD_PARTIAL if field_missing else RecordStatus.XINGTU_COMPLETED
                    result = XingtuEnrichmentRecord(
                        record_id=record.record_id,
                        creator_name=record.creator_name or "unknown",
                        status=record.status,
                        xingtu_id=detail.xingtu_id,
                        xingtu_profile_url=detail.xingtu_profile_url,
                        xingtu_creator_type=detail.xingtu_creator_type,
                        match_confidence=best_match.match_confidence,
                        match_reason=best_match.match_reason,
                        search_name_used=outcome.query,
                        price_20s=detail.price_20s,
                        price_20_60s=detail.price_20_60s,
                        price_60s_plus=detail.price_60s_plus,
                        estimated_play=detail.estimated_play,
                        sponsored_median_play=detail.sponsored_median_play,
                        natural_cpm=detail.natural_cpm,
                        cpe=detail.cpe,
                        sponsored_completion_rate=detail.sponsored_completion_rate,
                        monthly_fan_growth_rate=detail.monthly_fan_growth_rate,
                        monthly_connected_user_fan_ratio=detail.monthly_connected_user_fan_ratio,
                        monthly_deep_user_fan_ratio=detail.monthly_deep_user_fan_ratio,
                        recent_15_curve_screenshot_path=detail.recent_15_curve_screenshot_path,
                        cooperate_brands=detail.cooperate_brands,
                        field_missing_list=field_missing,
                        enrichment_notes="字段完整" if not field_missing else "部分字段当前页面不可见，已显式记录",
                        enrichment_status=status,
                        next_action=NextAction.DONE,
                    )
                    self.enrichment_store.append(result)
                    completed += 1
                except PageStructureUncertainError as exc:
                    result = XingtuEnrichmentRecord(
                        record_id=record.record_id,
                        creator_name=record.creator_name or "unknown",
                        status=record.status,
                        search_name_used=record.creator_name or "unknown",
                        match_confidence=MatchConfidence.LOW,
                        match_reason="星图页面结构不确定，未继续提取商业字段",
                        field_missing_list=["xingtu_id"],
                        enrichment_notes=exc.to_note(),
                        enrichment_status=RecordStatus.BLOCKED,
                        next_action=NextAction.RETRY_LATER,
                    )
                    self.enrichment_store.append(result)
                    blocked += 1
                except BlockingStateError:
                    raise

        duration_minutes = round((time.monotonic() - start_time) / 60, 2)
        return RunSummary(
            stage=WorkflowStage.XINGTU_ENRICHMENT,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=0,
            output_path=str(self.paths.enrichment_output),
            queue_path=str(self.paths.queue_output),
        )

    def _search_with_fallback(self, adapter: XingtuPageAdapter, record: CreatorDiscoveryRecord) -> XingtuSearchOutcome:
        creator_name = record.creator_name or "unknown"
        search_terms = [creator_name]
        compact = creator_name.replace(" ", "")
        if compact != creator_name:
            search_terms.append(compact)
        if len(compact) > 4:
            search_terms.append(compact[:4])
        tried = set()
        for term in search_terms:
            if not term or term in tried:
                continue
            tried.add(term)
            outcome = adapter.search(term)
            if outcome.result_kind != "not_found":
                return outcome
        return XingtuSearchOutcome(query=creator_name, result_kind="not_found")

    @staticmethod
    def _build_from_search_outcome(
        record: CreatorDiscoveryRecord,
        outcome: XingtuSearchOutcome,
    ) -> XingtuEnrichmentRecord | None:
        if outcome.result_kind == "not_found":
            return XingtuEnrichmentRecord(
                record_id=record.record_id,
                creator_name=record.creator_name or "unknown",
                status=record.status,
                search_name_used=outcome.query,
                match_confidence=MatchConfidence.LOW,
                match_reason="未在星图搜索结果中找到可匹配达人",
                field_missing_list=["xingtu_id", "xingtu_profile_url"],
                enrichment_status=RecordStatus.XINGTU_NOT_FOUND,
                next_action=NextAction.RETRY_LATER,
            )
        if outcome.result_kind == "unregistered":
            return XingtuEnrichmentRecord(
                record_id=record.record_id,
                creator_name=record.creator_name or "unknown",
                status=record.status,
                search_name_used=outcome.query,
                match_confidence=MatchConfidence.LOW,
                match_reason="可确认达人存在，但未在星图中以可用创作者身份出现",
                field_missing_list=["xingtu_id", "price_20s", "price_20_60s", "price_60s_plus"],
                enrichment_status=RecordStatus.XINGTU_UNREGISTERED,
                next_action=NextAction.DONE,
            )
        return None

    def _choose_best_candidate(self, record: CreatorDiscoveryRecord, outcome: XingtuSearchOutcome):
        decisions = [
            (
                candidate,
                evaluate_xingtu_match(
                    discovery_record=record,
                    candidate_name=candidate.candidate_name,
                    candidate_follower_hint=candidate.candidate_follower_hint,
                    candidate_creator_type=candidate.candidate_creator_type,
                    candidate_content_hint=candidate.candidate_content_hint,
                ),
            )
            for candidate in outcome.candidates
        ]
        high_confidence = [item for item in decisions if item[1].match_confidence == MatchConfidence.HIGH]
        if len(high_confidence) == 1:
            return high_confidence[0]
        if len(high_confidence) > 1:
            return None, None
        return None, None

    def _sleep_between_queries(self, page) -> None:
        seconds = random.uniform(
            self.run_config.min_query_interval_seconds,
            self.run_config.max_query_interval_seconds,
        )
        page.wait_for_timeout(int(seconds * 1_000))
