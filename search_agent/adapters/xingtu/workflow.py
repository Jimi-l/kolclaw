from __future__ import annotations

import logging
import random
import sys
import time

from search_agent.artifacts import ArtifactManager
from search_agent.browser.session import BrowserSession
from search_agent.config import BrowserConfig, EnrichmentRunConfig, RuntimePaths
from search_agent.enums import BlockReason, MatchConfidence, NextAction, RecordStatus, WorkflowStage
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError
from search_agent.models.common import MatchDecision, RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.enrichment import XingtuEnrichmentRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.storage.queue import XingtuQueueStore
from search_agent.utils.dedup import normalize_name

from . import selectors
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
        processed_ids = {
            record.record_id
            for record in existing_results
            if not self._should_retry_existing_result(record)
        }
        queued_records = self.queue_store.load_pending(processed_record_ids=processed_ids, limit=self.run_config.max_items)
        if not queued_records:
            self._backfill_queue_from_discovery(processed_record_ids=processed_ids)
            queued_records = self.queue_store.load_pending(processed_record_ids=processed_ids, limit=self.run_config.max_items)

        processed = completed = skipped = blocked = 0
        start_time = time.monotonic()

        with BrowserSession(self.browser_config, self.paths.browser_state_dir / "xingtu") as browser:
            adapter = XingtuPageAdapter(browser.page, self.artifacts, self.logger)
            self._open_homepage_with_recovery(adapter)

            for record in queued_records:
                processed += 1
                self._sleep_between_queries(browser.page)
                while True:
                    try:
                        handled = self._process_record(adapter, record)
                    except BlockingStateError as exc:
                        if self._handle_resumable_pause(exc, context=f"xingtu-record:{record.record_id}", adapter=adapter):
                            self._open_homepage_with_recovery(adapter)
                            continue
                        raise
                    if handled == RecordStatus.BLOCKED:
                        blocked += 1
                    elif handled in {RecordStatus.XINGTU_COMPLETED, RecordStatus.FIELD_PARTIAL}:
                        completed += 1
                    else:
                        skipped += 1
                    break

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

    def _should_retry_existing_result(self, record: XingtuEnrichmentRecord) -> bool:
        if self.run_config.retry_incomplete:
            return record.enrichment_status != RecordStatus.XINGTU_COMPLETED
        return self.run_config.retry_blocked and record.enrichment_status == RecordStatus.BLOCKED

    def _backfill_queue_from_discovery(self, processed_record_ids: set[str]) -> int:
        discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        queued_count = 0
        existing_queue_ids = {record.record_id for record in self.queue_store.store.load_all()}
        for record in discovery_store.load_all():
            if record.record_id in processed_record_ids or record.record_id in existing_queue_ids:
                continue
            if not record.is_ready_for_xingtu():
                continue
            payload = record.model_dump(mode="json")
            payload.update(
                {
                    "status": RecordStatus.QUEUED_FOR_XINGTU.value,
                    "next_action": NextAction.QUEUE_FOR_XINGTU.value,
                }
            )
            self.queue_store.enqueue(CreatorDiscoveryRecord.model_validate(payload))
            existing_queue_ids.add(record.record_id)
            queued_count += 1
        if queued_count:
            self.logger.info(
                "xingtu queue backfilled from discovery records",
                extra={
                    "queued_count": queued_count,
                    "discovery_path": str(self.paths.discovery_output),
                    "queue_path": str(self.paths.queue_output),
                },
            )
        return queued_count

    def _process_record(
        self,
        adapter: XingtuPageAdapter,
        record: CreatorDiscoveryRecord,
    ) -> RecordStatus:
        try:
            outcome = self._search_with_fallback(adapter, record)
            enrichment_record = self._build_from_search_outcome(record, outcome)
            if enrichment_record is not None:
                self.enrichment_store.append(enrichment_record)
                return enrichment_record.enrichment_status

            best_candidate, best_match = self._choose_best_candidate(record, outcome)
            if best_candidate is None or best_match is None:
                no_exact_name_match = self._exact_name_match_count(record, outcome) == 0
                ambiguous = XingtuEnrichmentRecord(
                    record_id=record.record_id,
                    creator_name=record.creator_name or "unknown",
                    status=record.status,
                    search_name_used=outcome.query,
                    match_confidence=MatchConfidence.LOW,
                    match_reason="搜索结果存在同名歧义，无法稳定确认同一达人",
                    field_missing_list=["xingtu_id", "xingtu_profile_url", "price_20s", "price_20_60s", "price_60s_plus"],
                    enrichment_status=RecordStatus.XINGTU_NOT_FOUND if no_exact_name_match else RecordStatus.AMBIGUOUS_MATCH,
                    next_action=NextAction.RETRY_LATER if no_exact_name_match else NextAction.MANUAL_REVIEW,
                )
                self.enrichment_store.append(ambiguous)
                return ambiguous.enrichment_status

            adapter.open_candidate(best_candidate)
            try:
                detail = adapter.extract_details(record.creator_name or "creator")
            finally:
                adapter.close_current_detail_page()
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
                price_insert_video=detail.price_insert_video,
                price_custom_video=detail.price_custom_video,
                price_douyin_image_text=detail.price_douyin_image_text,
                other_service_prices=detail.other_service_prices,
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
            return result.enrichment_status
        except PageStructureUncertainError as exc:
            if exc.resumable:
                raise
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
            return result.enrichment_status

    def _search_with_fallback(self, adapter: XingtuPageAdapter, record: CreatorDiscoveryRecord) -> XingtuSearchOutcome:
        creator_name = record.creator_name or "unknown"
        return adapter.search(creator_name)

    def _open_homepage_with_recovery(self, adapter: XingtuPageAdapter) -> None:
        while True:
            try:
                adapter.open_homepage()
                return
            except BlockingStateError as exc:
                if self._handle_resumable_pause(exc, context="xingtu-home", adapter=adapter):
                    continue
                raise

    def _handle_resumable_pause(self, exc: BlockingStateError, context: str, adapter: XingtuPageAdapter | None = None) -> bool:
        if not exc.resumable or not exc.needs_user_action:
            return False
        if exc.reason in self._login_block_reasons() and adapter is not None:
            return self._wait_until_creator_index_after_login(adapter, exc, context=context)
        if not sys.stdin.isatty():
            self.logger.warning(
                "xingtu resumable block cannot enter interactive pause without a tty",
                extra={
                    "context": context,
                    "reason": exc.reason.value,
                    "page_name": exc.page_name,
                    "page_state": exc.page_state,
                },
            )
            return False
        self.logger.warning(
            "xingtu entering interactive pause mode",
            extra={
                "context": context,
                "reason": exc.reason.value,
                "page_name": exc.page_name,
                "block_message": exc.message,
                "required_user_action": exc.required_user_action,
                "screenshot_path": exc.screenshot_path,
                "browser_will_remain_open": True,
            },
        )
        prompt_lines = [
            "",
            "Xingtu workflow is paused but resumable.",
            f"Context: {context}",
            f"Reason: {exc.reason.value}",
            f"Message: {exc.message}",
        ]
        if exc.required_user_action:
            prompt_lines.append(f"Action: {exc.required_user_action}")
        if self.browser_config.headless:
            prompt_lines.append("This workflow is running headless, so manual login/captcha recovery requires rerunning with a visible browser.")
        if exc.screenshot_path:
            prompt_lines.append(f"Screenshot: {exc.screenshot_path}")
        prompt_lines.append("Fix the page in the open browser, then press Enter to retry, or type q to quit.")
        print("\n".join(prompt_lines), flush=True)
        try:
            user_input = input().strip().lower()
        except EOFError:
            return False
        if user_input in {"q", "quit"}:
            raise BlockingStateError(
                reason=exc.reason,
                message=f"Operator quit during resumable Xingtu recovery: {context}",
                page_name=exc.page_name,
                page_state=exc.page_state,
                screenshot_path=exc.screenshot_path,
                required_user_action=exc.required_user_action,
                needs_user_action=exc.needs_user_action,
                resumable=exc.resumable,
            )
        self.logger.info("xingtu interactive retry requested", extra={"context": context, "browser_will_remain_open": True})
        return True

    def _wait_until_creator_index_after_login(
        self,
        adapter: XingtuPageAdapter,
        exc: BlockingStateError,
        context: str,
        max_wait_seconds: int = 600,
    ) -> bool:
        if self.browser_config.headless:
            self.logger.warning(
                "xingtu login block cannot be completed automatically in headless mode",
                extra={"context": context, "reason": exc.reason.value, "page_name": exc.page_name},
            )
            return False

        print(
            "\n".join(
                [
                    "",
                    "Xingtu login is required.",
                    f"Context: {context}",
                    f"Reason: {exc.reason.value}",
                    "Complete the login in the open browser. The workflow will continue automatically after /ad/creator/index loads.",
                ]
            ),
            flush=True,
        )
        self.logger.warning(
            "xingtu waiting for manual browser login to reach creator index",
            extra={
                "context": context,
                "reason": exc.reason.value,
                "page_name": exc.page_name,
                "screenshot_path": exc.screenshot_path,
                "target_url": selectors.CREATOR_BACKEND_HOME_URL,
                "browser_will_remain_open": True,
            },
        )

        deadline = time.monotonic() + max_wait_seconds
        last_logged_second = -1
        last_home_retry = 0.0
        while time.monotonic() < deadline:
            current_url = adapter.page.url
            if selectors.is_creator_backend_home_url(current_url):
                self.logger.info("xingtu login completed; creator index detected", extra={"context": context, "url": current_url})
                return True

            remaining = int(deadline - time.monotonic())
            if remaining // 30 != last_logged_second // 30:
                last_logged_second = remaining
                self.logger.info(
                    "xingtu still waiting for login redirect",
                    extra={"context": context, "current_url": current_url, "remaining_seconds": remaining},
                )

            page_text = ""
            try:
                page_text = adapter.page.locator("body").inner_text(timeout=800)
            except Exception:
                page_text = ""
            login_text_visible = any(hint in page_text for hint in selectors.LOGIN_HINTS + selectors.QR_LOGIN_HINTS + selectors.SMS_LOGIN_HINTS)

            now = time.monotonic()
            if selectors.has_creator_backend_redirect(current_url) and now - last_home_retry >= 2:
                last_home_retry = now
                self.logger.info(
                    "xingtu landed on redirect wrapper; navigating to creator index",
                    extra={"context": context, "current_url": current_url, "target_url": selectors.CREATOR_BACKEND_HOME_URL},
                )
                try:
                    adapter.page.goto(selectors.CREATOR_BACKEND_HOME_URL, wait_until="domcontentloaded")
                except Exception:
                    self.logger.debug("xingtu creator index redirect navigation failed", exc_info=True, extra={"context": context})
            elif not login_text_visible and now - last_home_retry >= 5:
                last_home_retry = now
                try:
                    adapter.page.goto(selectors.CREATOR_BACKEND_HOME_URL, wait_until="domcontentloaded")
                except Exception:
                    self.logger.debug("xingtu creator index retry navigation failed", exc_info=True, extra={"context": context})

            adapter.page.wait_for_timeout(1_000)

        raise BlockingStateError(
            reason=exc.reason,
            message=f"Xingtu login was not completed within {max_wait_seconds} seconds: {context}",
            page_name=exc.page_name,
            page_state=exc.page_state,
            screenshot_path=exc.screenshot_path,
            required_user_action=exc.required_user_action,
            needs_user_action=exc.needs_user_action,
            resumable=exc.resumable,
        )

    @staticmethod
    def _login_block_reasons() -> set[BlockReason]:
        return {
            BlockReason.LOGIN_REQUIRED,
            BlockReason.QR_LOGIN_REQUIRED,
            BlockReason.SMS_LOGIN_REQUIRED,
        }

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
        target_names = self._normalized_target_names(record, outcome)
        exact_name_matches = [
            candidate
            for candidate in outcome.candidates
            if normalize_name(candidate.candidate_name) in target_names
        ]
        if len(exact_name_matches) == 1:
            return exact_name_matches[0], MatchDecision(
                is_same_creator=True,
                match_confidence=MatchConfidence.HIGH,
                match_reason="Xingtu search returned exactly one candidate with the same normalized creator name.",
                conflict_points=[],
                next_action=NextAction.CONTINUE,
                score=6,
            )
        return None, None

    @staticmethod
    def _normalized_target_names(record: CreatorDiscoveryRecord, outcome: XingtuSearchOutcome) -> set[str]:
        return {
            name
            for name in (
                normalize_name(record.creator_name),
                normalize_name(outcome.query),
            )
            if name != "unknown"
        }

    @staticmethod
    def _exact_name_match_count(record: CreatorDiscoveryRecord, outcome: XingtuSearchOutcome) -> int:
        target_names = XingtuEnrichmentWorkflow._normalized_target_names(record, outcome)
        return sum(1 for candidate in outcome.candidates if normalize_name(candidate.candidate_name) in target_names)

    def _sleep_between_queries(self, page) -> None:
        seconds = random.uniform(
            self.run_config.min_query_interval_seconds,
            self.run_config.max_query_interval_seconds,
        )
        page.wait_for_timeout(int(seconds * 1_000))
