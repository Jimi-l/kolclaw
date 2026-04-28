from __future__ import annotations

import logging
import sys
import time
from datetime import date
from pathlib import Path

from search_agent.artifacts import ArtifactManager
from search_agent.browser.session import BrowserSession
from search_agent.config import BrowserConfig, ContentAnalysisRunConfig, DiscoveryRunConfig, RuntimePaths
from search_agent.enums import AnalysisStatus, BlockReason, NextAction, RecordStatus, WorkflowStage
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError, SearchAgentError
from search_agent.models.common import RunSummary, TaggingContext
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.storage.queue import ContentAnalysisQueueStore, XingtuQueueStore
from search_agent.tagging import HeuristicTagger
from search_agent.utils.dedup import build_duplicate_key, build_record_id, decide_duplicate
from search_agent.utils.normalize import normalize_chinese_count, normalize_publish_date, score_hotness_age
from search_agent.utils.trend import classify_traffic_trend

from .content_analysis import ContentAnalysisWorkflow
from .page import DouyinPageAdapter, FeedCandidateSnapshot, HomepageBrowseResult


class CreatorDiscoveryWorkflow:
    REPEATED_UNKNOWN_LIMIT = 3
    STALLED_FEED_LIMIT = 2
    RESUME_ATTEMPT_LIMIT = 2

    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        browser_config: BrowserConfig,
        run_config: DiscoveryRunConfig,
    ):
        self.paths = paths
        self.artifacts = artifacts
        self.browser_config = browser_config
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.discovery")
        self.tagger = HeuristicTagger()
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.queue_store = XingtuQueueStore(self.paths.queue_output)
        self.analysis_queue_store = ContentAnalysisQueueStore(self.paths.analysis_queue_output)

    def bootstrap_login(self) -> dict:
        self.paths.ensure_directories()
        session_path = self._session_path()
        start_time = time.monotonic()
        deadline = self._deadline_at(start_time)

        with BrowserSession(self.browser_config, session_path) as browser:
            self._log_session_state(browser, session_path, mode="bootstrap-login")
            adapter = DouyinPageAdapter(browser.page, self.artifacts, self.logger)
            adapter.open_homepage()
            snapshot = self._run_with_interactive_pause(
                adapter=adapter,
                operation=lambda: adapter.ensure_normal_feed(bootstrap_login=True),
                context="bootstrap-login",
                deadline=deadline,
            )
            self.logger.info(
                "douyin bootstrap login completed",
                extra={
                    "session_path": str(session_path),
                    "reused_persisted_session": browser.reused_existing_session,
                    "login_detected": self._is_feed_loop_ready_state(snapshot.state),
                    "page_state": snapshot.state,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                },
            )
            return {
                "stage": WorkflowStage.CREATOR_DISCOVERY.value,
                "mode": "bootstrap-login",
                "run_id": self.artifacts.run_id,
                "session_path": str(session_path),
                "reused_persisted_session": browser.reused_existing_session,
                "login_ready": self._is_feed_loop_ready_state(snapshot.state),
                "page_state": snapshot.state,
                "page_url": snapshot.page_url,
                "page_title": snapshot.page_title,
                "message": "Douyin bootstrap-only step completed and the recommend feed is interactable. Rerun creator-discovery without --bootstrap-login to execute the F/homepage/scroll browse loop.",
                "next_command": "python -m search_agent creator-discovery --browser-channel chrome --max-candidates 5 --max-minutes 5 --log-level INFO",
            }

    def run(self) -> RunSummary:
        self.paths.ensure_directories()
        existing_records = self.discovery_store.load_all()
        processed = qualified = skipped = blocked = 0
        observation_count = 0
        records_for_analysis: set[str] = set()
        start_time = time.monotonic()
        stalled_feed_streak = 0
        session_path = self._session_path()
        deadline = self._deadline_at(start_time)

        with BrowserSession(self.browser_config, session_path) as browser:
            self._log_session_state(browser, session_path, mode="creator-discovery")
            adapter = DouyinPageAdapter(browser.page, self.artifacts, self.logger)
            adapter.open_homepage()
            bootstrap_state = self._run_with_interactive_pause(
                adapter=adapter,
                operation=lambda: adapter.ensure_normal_feed(bootstrap_login=False),
                context="discovery-bootstrap",
                deadline=deadline,
            )
            self.logger.info(
                "douyin discovery feed ready",
                extra={
                    "session_path": str(session_path),
                    "login_detected": self._is_feed_loop_ready_state(bootstrap_state.state),
                    "page_state": bootstrap_state.state,
                    "page_url": bootstrap_state.page_url,
                    "page_title": bootstrap_state.page_title,
                },
            )

            while processed < self.run_config.max_candidates:
                if self.run_config.stop_event is not None and self.run_config.stop_event.is_set():
                    break
                elapsed_minutes = (time.monotonic() - start_time) / 60
                if elapsed_minutes >= self.run_config.max_minutes:
                    break

                observation_count += 1
                processed += 1
                debug_label = f"{observation_count:03d}"
                cycle = self._browse_cycle_with_resume(
                    adapter=adapter,
                    observation_index=observation_count,
                    debug_label=debug_label,
                    deadline=deadline,
                )
                self._log_browse_cycle(cycle)
                minimal_record = self._build_discovery_record(cycle)
                duplicate_decision = (
                    decide_duplicate(minimal_record, existing_records)
                    if self._should_check_duplicate(minimal_record)
                    else None
                )
                if duplicate_decision and duplicate_decision.is_duplicate and not duplicate_decision.requires_manual_review:
                    skipped += 1
                    self.logger.info(
                        "discovery record skipped as duplicate",
                        extra={
                            "record_id": minimal_record.record_id,
                            "matched_record_id": duplicate_decision.matched_record_id,
                            "reason": duplicate_decision.reason,
                        },
                    )
                else:
                    content_snapshot = self._collect_content_snapshot_with_resume(
                        adapter=adapter,
                        candidate=cycle.feed_snapshot,
                        debug_label=debug_label,
                        deadline=deadline,
                    )
                    final_cycle = HomepageBrowseResult(
                        observation_index=cycle.observation_index,
                        feed_snapshot=content_snapshot,
                        profile_snapshot=cycle.profile_snapshot,
                        homepage_screenshot_path=cycle.homepage_screenshot_path,
                        homepage_page_url=cycle.homepage_page_url,
                        homepage_page_title=cycle.homepage_page_title,
                        homepage_open_state=cycle.homepage_open_state,
                        homepage_close_state=cycle.homepage_close_state,
                    )
                    record = self._build_discovery_record(final_cycle)
                    self.discovery_store.append(record)
                    existing_records.append(record)
                    if self.run_config.content_analysis_enabled:
                        self.analysis_queue_store.enqueue(record)
                        records_for_analysis.add(record.record_id)
                    qualified += 1
                    self.logger.info(
                        "discovery record saved",
                        extra={
                            "record_id": record.record_id,
                            "creator_name": record.creator_name,
                            "video_url": record.video_url,
                            "follower_count_raw": record.follower_count_raw,
                            "total_interaction_text": record.total_interaction_text,
                            "status": getattr(record.status, "value", record.status),
                            "next_action": getattr(record.next_action, "value", record.next_action),
                        },
                    )

                self.logger.info(
                    "scrolling to next video",
                    extra={
                        "observation_index": observation_count,
                        "feed_identity": cycle.feed_snapshot.feed_identity,
                        "page_url": cycle.feed_snapshot.page_url,
                        "page_title": cycle.feed_snapshot.page_title,
                    },
                )
                movement = self._run_with_interactive_pause(
                    adapter=adapter,
                    operation=lambda: adapter.advance_feed(cycle.feed_snapshot, debug_label=f"{debug_label}_post"),
                    context=f"feed-scroll:{debug_label}",
                    deadline=deadline,
                )
                self._log_feed_progression(movement, observation_count)
                if movement.changed:
                    stalled_feed_streak = 0
                    continue
                stalled_feed_streak += 1
                if stalled_feed_streak >= self.STALLED_FEED_LIMIT:
                    exc = self._build_feed_debug_exception(
                        cycle.feed_snapshot,
                        message="完成主页开关后滚动未进入下一条视频，当前推荐流停滞。",
                        movement=movement,
                    )
                    if self._handle_resumable_pause(adapter, exc, context="stalled-feed", deadline=deadline):
                        stalled_feed_streak = 0
                        continue
                    raise exc

        analysis_processed = 0
        if self.run_config.content_analysis_enabled and records_for_analysis:
            analysis_workflow = ContentAnalysisWorkflow(
                paths=self.paths,
                artifacts=self.artifacts,
                run_config=ContentAnalysisRunConfig(
                    enabled=True,
                    max_items=self.run_config.analysis_max_items or len(records_for_analysis),
                    keyframe_count=self.run_config.analysis_keyframes,
                    model_name=self.run_config.analysis_model,
                ),
            )
            analysis_summary = analysis_workflow.run(priority_record_ids=records_for_analysis)
            analysis_processed = analysis_summary.processed_candidates
            self.logger.info(
                "content analysis stage completed",
                extra={
                    "processed_candidates": analysis_summary.processed_candidates,
                    "successful_records": analysis_summary.successful_records,
                    "skipped_items": analysis_summary.skipped_items,
                    "blocked_items": analysis_summary.blocked_items,
                    "output_path": analysis_summary.output_path,
                },
            )

        duration_minutes = round((time.monotonic() - start_time) / 60, 2)
        return RunSummary(
            stage=WorkflowStage.CREATOR_DISCOVERY,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=qualified,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=analysis_processed,
            output_path=str(self.paths.discovery_output),
            queue_path=str(self.paths.analysis_queue_output),
        )

    @staticmethod
    def _screen_candidate(candidate: FeedCandidateSnapshot) -> str | None:
        if candidate.is_ad:
            return "广告内容，直接跳过"
        if candidate.is_live:
            return "直播间内容，不进入普通短视频分析链路"
        threshold_hits = [
            (normalize_chinese_count(candidate.like_count_raw) or 0) >= 200_000,
            (normalize_chinese_count(candidate.share_count_raw) or 0) >= 100_000,
            (normalize_chinese_count(candidate.favorite_count_raw) or 0) >= 100_000,
            (normalize_chinese_count(candidate.comment_count_raw) or 0) >= 10_000,
        ]
        if not any(threshold_hits):
            return "点赞、评论、收藏、转发均未达到潜力阈值"
        if not candidate.creator_name or not candidate.total_interaction_text:
            return "达人名称或互动数据无法稳定提取"
        return None

    def _build_skip_record(self, candidate: FeedCandidateSnapshot, reason: str) -> CreatorDiscoveryRecord:
        creator_name = candidate.creator_name or "unknown"
        return CreatorDiscoveryRecord(
            record_id=build_record_id(creator_name, collection_date=date.today()),
            workflow_run_id=self.run_config.workflow_run_id,
            status=RecordStatus.SKIPPED,
            collection_date=date.today().strftime("%Y/%m/%d"),
            video_url=candidate.video_url,
            publish_time_raw=candidate.publish_time_raw,
            total_interaction_text=candidate.total_interaction_text,
            like_count_raw=candidate.like_count_raw,
            comment_count_raw=candidate.comment_count_raw,
            favorite_count_raw=candidate.favorite_count_raw,
            share_count_raw=candidate.share_count_raw,
            creator_name=creator_name,
            duplicate_key=build_duplicate_key("douyin", creator_name),
            next_action=NextAction.SKIP,
            notes="；".join(filter(None, [reason, self._candidate_debug_note(candidate)])),
        )

    def _build_blocked_record(self, candidate: FeedCandidateSnapshot, exc: BlockingStateError) -> CreatorDiscoveryRecord:
        creator_name = candidate.creator_name or "unknown"
        return CreatorDiscoveryRecord(
            record_id=build_record_id(creator_name, collection_date=date.today()),
            workflow_run_id=self.run_config.workflow_run_id,
            status=RecordStatus.BLOCKED,
            collection_date=date.today().strftime("%Y/%m/%d"),
            video_url=candidate.video_url,
            publish_time_raw=candidate.publish_time_raw,
            total_interaction_text=candidate.total_interaction_text,
            like_count_raw=candidate.like_count_raw,
            comment_count_raw=candidate.comment_count_raw,
            favorite_count_raw=candidate.favorite_count_raw,
            share_count_raw=candidate.share_count_raw,
            creator_name=creator_name,
            duplicate_key=build_duplicate_key("douyin", creator_name),
            next_action=NextAction.MANUAL_REVIEW,
            notes="；".join(filter(None, [exc.to_note(), self._candidate_debug_note(candidate)])),
        )

    def _analyze_creator_with_resume(
        self,
        adapter: DouyinPageAdapter,
        candidate: FeedCandidateSnapshot,
        deadline: float | None,
    ):
        return self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.analyze_creator(candidate),
            context=f"analyze-creator:{candidate.creator_name or 'unknown'}",
            deadline=deadline,
        )

    def _read_candidate_with_resume(
        self,
        adapter: DouyinPageAdapter,
        debug_label: str,
        deadline: float | None,
    ) -> FeedCandidateSnapshot:
        self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.ensure_normal_feed(bootstrap_login=False),
            context=f"candidate-feed-gate:{debug_label}",
            deadline=deadline,
        )
        return self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.read_current_candidate(debug_label=debug_label),
            context=f"candidate-read:{debug_label}",
            deadline=deadline,
        )

    def _browse_cycle_with_resume(
        self,
        adapter: DouyinPageAdapter,
        observation_index: int,
        debug_label: str,
        deadline: float | None,
    ) -> HomepageBrowseResult:
        self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.ensure_normal_feed(bootstrap_login=False),
            context=f"browse-feed-gate:{debug_label}",
            deadline=deadline,
        )
        return self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.browse_creator_homepage_cycle(
                observation_index=observation_index,
                debug_label=debug_label,
            ),
            context=f"browse-cycle:{debug_label}",
            deadline=deadline,
        )

    def _collect_content_snapshot_with_resume(
        self,
        adapter: DouyinPageAdapter,
        candidate: FeedCandidateSnapshot,
        debug_label: str,
        deadline: float | None,
    ) -> FeedCandidateSnapshot:
        return self._run_with_interactive_pause(
            adapter=adapter,
            operation=lambda: adapter.collect_content_snapshot(
                candidate,
                debug_label=debug_label,
                keyframe_count=self.run_config.analysis_keyframes,
            ),
            context=f"content-snapshot:{debug_label}",
            deadline=deadline,
        )

    def _run_with_interactive_pause(
        self,
        adapter: DouyinPageAdapter,
        operation,
        context: str,
        deadline: float | None,
    ):
        paused_once = False
        while True:
            self._ensure_within_deadline(deadline, context)
            try:
                result = operation()
                if paused_once:
                    self.logger.info(
                        "douyin retry succeeded after Enter",
                        extra={"context": context, "browser_will_remain_open": True},
                    )
                return result
            except BlockingStateError as exc:
                if not self._handle_resumable_pause(adapter, exc, context=context, deadline=deadline):
                    raise
                paused_once = True
            except Exception as exc:
                if adapter.maybe_recover_from_target_closed(exc, context=context):
                    recovery_exc = BlockingStateError(
                        reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                        message="Douyin 页面在操作过程中被关闭，已尝试在同一持久化 session 中重新打开。",
                        page_name=context,
                        page_state="page_reopened_after_close",
                        required_user_action="Please confirm the reopened page is back on normal Douyin web content, then press Enter to retry.",
                        needs_user_action=True,
                        resumable=True,
                    )
                    if not self._handle_resumable_pause(adapter, recovery_exc, context=context, deadline=deadline):
                        raise
                    paused_once = True
                    continue
                raise

    def _handle_resumable_pause(
        self,
        adapter: DouyinPageAdapter,
        exc: BlockingStateError,
        context: str,
        deadline: float | None,
    ) -> bool:
        if not exc.resumable or not exc.needs_user_action:
            return False
        if not sys.stdin.isatty():
            self.logger.warning(
                "douyin resumable block cannot enter interactive pause without a tty",
                extra={
                    "context": context,
                    "reason": exc.reason.value,
                    "page_state": exc.page_state,
                },
            )
            return False
        self._ensure_within_deadline(deadline, context)
        self.logger.warning(
            "douyin entering interactive pause mode",
            extra={
                "context": context,
                "reason": exc.reason.value,
                "page_name": exc.page_name,
                "page_state": exc.page_state,
                "block_message": exc.message,
                "required_user_action": exc.required_user_action,
                "screenshot_path": exc.screenshot_path,
                "browser_will_remain_open": True,
            },
        )
        remaining_minutes = self._remaining_minutes(deadline)
        if exc.page_state in {
            "public_jingxuan_landing",
            "jingxuan_ready_to_enter_recommend",
            "jingxuan_blocked_by_external_app_prompt",
        }:
            prompt_lines = [
                "",
                "Blocked on jingxuan/open-app.",
                f"Context: {context}",
                f"Reason: {exc.reason.value}",
                f"Page state: {exc.page_state or 'unknown'}",
                f"Message: {exc.message}",
                "If Chrome shows 'Open xdg-open?': uncheck 'Always allow ...' if it is checked, then click Cancel.",
                "Keep the page on /jingxuan.",
                "After pressing Enter here, the workflow will retry entering the 推荐 feed.",
            ]
        elif exc.page_state in {"recommend_feed_shell", "creator_homepage_open", "self_profile_open"}:
            prompt_lines = [
                "",
                "Recommend/feed interaction is paused but resumable.",
                f"Context: {context}",
                f"Reason: {exc.reason.value}",
                f"Page state: {exc.page_state or 'unknown'}",
                f"Message: {exc.message}",
                "Keep the browser on the current Douyin web page.",
                "If the feed looks half-hydrated, wait for the center video card to stabilize.",
                "If the creator homepage is still open, leave it visible unless you are explicitly asked to close it.",
            ]
        else:
            prompt_lines = [
                "",
                "Blocked but resumable.",
                f"Context: {context}",
                f"Reason: {exc.reason.value}",
                f"Page state: {exc.page_state or 'unknown'}",
                f"Message: {exc.message}",
            ]
        if exc.required_user_action:
            prompt_lines.append(f"Action: {exc.required_user_action}")
        if self.browser_config.headless:
            prompt_lines.append(
                "This workflow is running headless, so manual recovery is limited. Rerun live discovery with --no-headless to handle captcha/popups in a visible Chrome window."
            )
        if exc.screenshot_path:
            prompt_lines.append(f"Screenshot: {exc.screenshot_path}")
        if remaining_minutes is not None:
            prompt_lines.append(f"Time remaining: {remaining_minutes:.1f} minutes")
        prompt_lines.append("Fix the page in the open browser, then press Enter to retry, or type q to quit.")
        print("\n".join(prompt_lines), flush=True)
        try:
            user_input = input().strip().lower()
        except EOFError:
            return False
        if user_input in {"q", "quit"}:
            raise SearchAgentError(f"Operator quit during resumable Douyin recovery: {context}")
        if exc.page_state in {
            "public_jingxuan_landing",
            "jingxuan_ready_to_enter_recommend",
            "jingxuan_blocked_by_external_app_prompt",
        }:
            adapter.prepare_jingxuan_retry_after_operator_recovery()
        self.logger.info(
            "douyin interactive retry requested",
            extra={"context": context, "browser_will_remain_open": True},
        )
        return True

    def _deadline_at(self, start_time: float) -> float | None:
        if self.run_config.max_minutes <= 0:
            return None
        return start_time + (self.run_config.max_minutes * 60)

    def _ensure_within_deadline(self, deadline: float | None, context: str) -> None:
        if deadline is None:
            return
        if time.monotonic() <= deadline:
            return
        raise SearchAgentError(f"Douyin workflow timed out while waiting for manual recovery: {context}")

    @staticmethod
    def _remaining_minutes(deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return max(0.0, (deadline - time.monotonic()) / 60)

    def _session_path(self) -> Path:
        return self.paths.browser_state_dir / "douyin"

    def _log_session_state(self, browser: BrowserSession, session_path: Path, mode: str) -> None:
        self.logger.info(
            "douyin persistent session opened",
            extra={
                "mode": mode,
                "session_path": str(session_path),
                "reused_persisted_session": browser.reused_existing_session,
                "headless": self.browser_config.headless,
                "browser_channel": self.browser_config.channel,
                "persisted_session_present": browser.reused_existing_session,
            },
        )

    def _log_candidate_observation(self, candidate: FeedCandidateSnapshot, observation_index: int) -> None:
        self.logger.info(
            "candidate observed",
            extra={
                "observation_index": observation_index,
                "page_url": candidate.page_url,
                "page_title": candidate.page_title,
                "feed_identity": candidate.feed_identity,
                "feed_selector_hint": candidate.feed_selector_hint,
                "creator_name": candidate.creator_name,
                "video_url": candidate.video_url,
                "active_text_summary": candidate.active_text_summary,
                "pre_extract_screenshot_path": candidate.pre_extract_screenshot_path,
            },
        )

    def _log_browse_cycle(self, cycle: HomepageBrowseResult) -> None:
        candidate = cycle.feed_snapshot
        profile = cycle.profile_snapshot
        self.logger.info(
            "browse loop iteration completed",
            extra={
                "observation_index": cycle.observation_index,
                "feed_identity": candidate.feed_identity,
                "page_url": candidate.page_url,
                "page_title": candidate.page_title,
                "creator_name": candidate.creator_name,
                "video_url": candidate.video_url,
                "active_text_summary": candidate.active_text_summary,
                "homepage_open_state": cycle.homepage_open_state,
                "homepage_close_state": cycle.homepage_close_state,
                "homepage_page_url": cycle.homepage_page_url,
                "homepage_page_title": cycle.homepage_page_title,
                "homepage_screenshot_path": cycle.homepage_screenshot_path,
                "profile_creator_name": profile.creator_name if profile else None,
                "profile_follower_count_raw": profile.follower_count_raw if profile else None,
                "profile_total_liked_count_raw": profile.total_liked_count_raw if profile else None,
            },
        )

    def _log_feed_progression(self, movement, observation_index: int) -> None:
        self.logger.info(
            "feed progression",
            extra={
                "observation_index": observation_index,
                "changed": movement.changed,
                "before_identity": movement.before_identity,
                "after_identity": movement.after_identity,
                "before_summary": movement.before_summary,
                "after_summary": movement.after_summary,
                "page_url": movement.page_url,
                "page_title": movement.page_title,
                "post_scroll_screenshot_path": movement.screenshot_path,
                "debug_label": movement.debug_label,
            },
        )

    @staticmethod
    def _candidate_identity(candidate: FeedCandidateSnapshot) -> str | None:
        return candidate.feed_identity or candidate.video_url or candidate.creator_profile_url or candidate.active_text_summary

    @staticmethod
    def _unknown_signature(candidate: FeedCandidateSnapshot) -> str | None:
        has_identity = bool(candidate.creator_name and candidate.creator_name.strip())
        has_video = bool(candidate.video_url)
        has_interactions = bool(candidate.total_interaction_text)
        if has_identity and has_video and has_interactions:
            return None
        return candidate.feed_identity or candidate.active_text_summary or candidate.page_url

    @staticmethod
    def _candidate_debug_note(candidate: FeedCandidateSnapshot) -> str:
        parts = [
            f"page_url={candidate.page_url}" if candidate.page_url else None,
            f"page_title={candidate.page_title}" if candidate.page_title else None,
            f"feed_identity={candidate.feed_identity}" if candidate.feed_identity else None,
            f"active_text_summary={candidate.active_text_summary}" if candidate.active_text_summary else None,
            f"pre_extract_screenshot={candidate.pre_extract_screenshot_path}" if candidate.pre_extract_screenshot_path else None,
        ]
        return " | ".join(part for part in parts if part)

    @staticmethod
    def _is_feed_loop_ready_state(state: str | None) -> bool:
        return state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}

    def _build_discovery_record(self, cycle: HomepageBrowseResult) -> CreatorDiscoveryRecord:
        candidate = cycle.feed_snapshot
        profile = cycle.profile_snapshot
        creator_name = (profile.creator_name if profile else None) or candidate.creator_name or candidate.creator_profile_url or "unknown"
        follower_count_raw = profile.follower_count_raw if profile else None
        follower_count_normalized = normalize_chinese_count(follower_count_raw)
        profile_bio = profile.profile_bio if profile else None
        tagging = self.tagger.tag(
            TaggingContext(
                creator_name=(profile.creator_name if profile else None) or candidate.creator_name,
                profile_bio=profile_bio,
                follower_count_raw=follower_count_raw,
                total_liked_count_raw=profile.total_liked_count_raw if profile else None,
                recommendation_video_summary=candidate.active_text_summary or candidate.caption_text,
                video_description_raw=candidate.video_description_raw,
                video_title_text=candidate.video_title_text,
                expanded_description_text=candidate.expanded_description_text,
                video_text_bundle=candidate.video_text_bundle,
                chapter_texts=candidate.chapter_texts,
                related_search_terms=candidate.related_search_terms,
                author_statement_texts=candidate.author_statement_texts,
                recent_videos_summary=profile.recent_video_titles if profile else [],
                visible_subtitle_segments=candidate.visible_subtitle_segments,
                top_comments=candidate.top_comments,
                visible_scenes=profile.visible_scenes if profile else [],
                speaking_style=profile.speaking_style if profile else None,
                video_duration_pattern=profile.video_duration_pattern if profile else None,
                ai_generated_flag=candidate.ai_generated_flag,
                extra_notes=profile_bio,
            )
        )
        notes = "；".join(
            part
            for part in [
                "内容快照已采集",
                f"homepage_screenshot={cycle.homepage_screenshot_path}" if cycle.homepage_screenshot_path else None,
                f"feed_summary={candidate.active_text_summary}" if candidate.active_text_summary else None,
                "video_url_missing" if not candidate.video_url else None,
                "top_comments_missing" if not candidate.top_comments else None,
                f"top_comments_source={candidate.top_comments_source}" if candidate.top_comments_source else None,
                (
                    f"comment_collection_status={candidate.comment_collection_status}"
                    if candidate.comment_collection_status
                    else None
                ),
                f"comment_collection_debug={candidate.comment_collection_debug}" if candidate.comment_collection_debug else None,
                "subtitles_missing" if not candidate.visible_subtitle_segments else None,
                "related_search_missing" if not candidate.related_search_terms else None,
                "author_statement_missing" if not candidate.author_statement_texts else None,
            ]
            if part
        )
        return CreatorDiscoveryRecord(
            record_id=build_record_id(creator_name, collection_date=date.today()),
            workflow_run_id=self.run_config.workflow_run_id,
            status=RecordStatus.DISCOVERED,
            collection_date=date.today().strftime("%Y/%m/%d"),
            video_url=candidate.video_url,
            video_url_capture_source=candidate.video_url_capture_source or "none",
            publish_time_raw=candidate.publish_time_raw,
            publish_date_normalized=normalize_publish_date(candidate.publish_time_raw),
            hotness_age_score=score_hotness_age(candidate.publish_time_raw),
            total_interaction_text=candidate.total_interaction_text,
            like_count_raw=candidate.like_count_raw,
            comment_count_raw=candidate.comment_count_raw,
            favorite_count_raw=candidate.favorite_count_raw,
            share_count_raw=candidate.share_count_raw,
            ai_generated_flag=candidate.ai_generated_flag,
            active_text_summary=candidate.active_text_summary,
            video_title_text=candidate.video_title_text,
            video_description_raw=candidate.video_description_raw,
            expanded_description_text=candidate.expanded_description_text,
            video_text_bundle=candidate.video_text_bundle,
            chapter_texts=candidate.chapter_texts,
            related_search_terms=candidate.related_search_terms,
            author_statement_texts=candidate.author_statement_texts,
            visible_subtitle_segments=candidate.visible_subtitle_segments,
            top_comments=candidate.top_comments,
            top_comments_source=candidate.top_comments_source or "none",
            comment_collection_status=candidate.comment_collection_status,
            comment_collection_debug=candidate.comment_collection_debug,
            keyframe_paths=candidate.keyframe_paths,
            creator_name=(profile.creator_name if profile else None) or candidate.creator_name,
            follower_count_raw=follower_count_raw,
            follower_count_normalized=follower_count_normalized,
            total_liked_count_raw=profile.total_liked_count_raw if profile else None,
            profile_bio=profile_bio,
            recent_video_titles=profile.recent_video_titles if profile else [],
            visible_scenes=profile.visible_scenes if profile else [],
            speaking_style=profile.speaking_style if profile else None,
            video_duration_pattern=profile.video_duration_pattern if profile else None,
            recommendation_video_like_raw=candidate.like_count_raw,
            content_taxonomy_path=tagging.content_taxonomy_path,
            content_leaf_tags=tagging.content_leaf_tags,
            profession_tags=tagging.profession_tags,
            interest_tags=tagging.interest_tags,
            life_tags=tagging.life_tags,
            appearance_relation_tags=tagging.appearance_relation_tags,
            monetization=tagging.monetization,
            cooperate_type=tagging.cooperate_type,
            analysis_status=AnalysisStatus.PENDING if self.run_config.content_analysis_enabled else None,
            analysis_backend="pending" if self.run_config.content_analysis_enabled else None,
            analysis_model=self.run_config.analysis_model if self.run_config.content_analysis_enabled else None,
            tagging_reasoning=tagging.label_reasoning,
            notes=notes,
            duplicate_key=build_duplicate_key("douyin", (profile.creator_name if profile else None) or candidate.creator_name or creator_name),
            next_action=NextAction.CONTINUE,
        )

    @staticmethod
    def _should_check_duplicate(record: CreatorDiscoveryRecord) -> bool:
        creator_name = (record.creator_name or "").strip().lower()
        if not creator_name or creator_name in {"unknown", "我的"}:
            return False
        return bool(record.video_url or record.follower_count_raw or record.total_interaction_text)

    def _build_feed_debug_exception(
        self,
        candidate: FeedCandidateSnapshot,
        message: str,
        movement=None,
    ) -> PageStructureUncertainError:
        debug_lines = [
            f"message={message}",
            f"page_url={candidate.page_url}",
            f"page_title={candidate.page_title}",
            f"feed_identity={candidate.feed_identity}",
            f"feed_selector_hint={candidate.feed_selector_hint}",
            f"creator_name={candidate.creator_name}",
            f"video_url={candidate.video_url}",
            f"total_interaction_text={candidate.total_interaction_text}",
            f"active_text_summary={candidate.active_text_summary}",
            f"pre_extract_screenshot_path={candidate.pre_extract_screenshot_path}",
        ]
        screenshot_path = candidate.pre_extract_screenshot_path
        if movement is not None:
            debug_lines.extend(
                [
                    f"scroll_changed={movement.changed}",
                    f"before_identity={movement.before_identity}",
                    f"after_identity={movement.after_identity}",
                    f"before_summary={movement.before_summary}",
                    f"after_summary={movement.after_summary}",
                    f"post_scroll_screenshot_path={movement.screenshot_path}",
                    f"post_scroll_page_url={movement.page_url}",
                    f"post_scroll_page_title={movement.page_title}",
                ]
            )
            screenshot_path = movement.screenshot_path or screenshot_path
        debug_artifact = self.artifacts.write_text(
            f"douyin_feed_debug_{int(time.time())}",
            debug_lines,
        )
        return PageStructureUncertainError(
            reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            message=message,
            page_name="douyin_feed",
            screenshot_path=screenshot_path,
            required_user_action=(
                "Please scroll to a stable active card, dismiss overlays, wait for feed hydration, or provide a fresh screenshot / DOM snapshot of the active Douyin feed item. "
                f"Debug artifact: {debug_artifact}"
            ),
            needs_user_action=True,
            resumable=True,
        )
