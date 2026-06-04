from __future__ import annotations

import csv
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path
from textwrap import shorten

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


#添加污染检测函数
POLLUTED_PAGE_HINTS = [
    "开启读屏标签",
    "读屏标签已关闭",
    "下载抖音精选",
    "京ICP备",
    "京公网安备",
    "广播电视节目制作经营许可证",
    "增值电信业务经营许可证",
    "网络文化经营许可证",
    "互联网宗教信息服务许可证",
    "用户服务协议",
    "隐私政策",
    "账号找回",
    "联系我们",
    "加入我们",
    "营业执照",
    "友情链接",
    "站点地图",
]


def _looks_like_polluted_page_text(text: str | None) -> bool:
    if not text:
        return False

    return any(hint in text for hint in POLLUTED_PAGE_HINTS)


def _snapshot_is_polluted(snapshot) -> bool:
    text_parts = [
        getattr(snapshot, "raw_text", None),
        getattr(snapshot, "description", None),
        getattr(snapshot, "description_text", None),
        getattr(snapshot, "expanded_description_text", None),
        getattr(snapshot, "active_text_summary", None),
    ]

    combined_text = "\n".join(part for part in text_parts if part)

    return _looks_like_polluted_page_text(combined_text)

def _value(obj, *names, default=None):
    """Safely read a value from dict/object using several possible field names."""
    for name in names:
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)

        if value is not None and value != "":
            return value

    return default


def _print_discovery_record_to_terminal(record, snapshot=None, homepage_result=None) -> None:
    """Print one discovery record in a clear human-readable terminal block."""

    record_id = _value(record, "record_id", "id", default="")
    creator_name = _value(record, "creator_name", default="")
    video_url = _value(record, "video_url", default=None)
    video_url_capture_source = _value(record, "video_url_capture_source", default=None)

    follower_count_raw = _value(
        record,
        "follower_count_raw",
        "profile_follower_count_raw",
        default=None,
    )

    total_liked_count_raw = _value(
        record,
        "total_liked_count_raw",
        "profile_total_liked_count_raw",
        default=None,
    )

    total_interaction_text = _value(record, "total_interaction_text", default=None)

    description = _value(
        record,
        "description",
        "description_text",
        "expanded_description_text",
        "active_text_summary",
        default=None,
    )

    homepage_open_state = _value(record, "homepage_open_state", default=None)
    homepage_close_state = _value(record, "homepage_close_state", default=None)
    comment_collection_status = _value(record, "comment_collection_status", default=None)
    comment_count = _value(record, "comment_count", default=None)

    print("\n" + "=" * 90)
    print("DISCOVERY RECORD SAVED")
    print("=" * 90)
    print(f"record_id: {record_id}")
    print(f"creator_name: {creator_name}")
    print("-" * 90)
    print(f"profile_follower_count_raw: {follower_count_raw}")
    print(f"profile_total_liked_count_raw: {total_liked_count_raw}")
    print("-" * 90)
    print(f"total_interaction_text: {total_interaction_text}")
    print(f"video_url: {video_url}")
    print(f"video_url_capture_source: {video_url_capture_source}")
    print("-" * 90)
    print(f"homepage_open_state: {homepage_open_state}")
    print(f"homepage_close_state: {homepage_close_state}")
    print(f"comment_collection_status: {comment_collection_status}")
    print(f"comment_count: {comment_count}")
    print("-" * 90)
    print("description:")
    print(description or "")
    print("=" * 90 + "\n")

# 在 helper 区域加表格函数
def _short_text(value, width: int = 18) -> str:
    """Shorten long text for terminal table display."""
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    if not text:
        return ""
    return shorten(text, width=width, placeholder="...")


def _table_value(record, *names, default=""):
    """Read one value from record using possible field names."""
    for name in names:
        value = getattr(record, name, None)
        if value is not None and value != "":
            return value
    return default


def _print_discovery_records_table(records: list) -> None:
    """Print all saved discovery records from this run as a readable terminal table."""
    if not records:
        print("\nNo discovery records saved in this run.\n")
        return

    headers = [
        "No",
        "达人",
        "粉丝",
        "获赞",
        "视频互动",
        "视频链接",
        "评论状态",
        "record_id",
    ]

    rows = []

    for index, record in enumerate(records, start=1):
        video_url = _table_value(record, "video_url", default="")
        video_url_status = "yes" if video_url else "no"

        rows.append(
            [
                str(index),
                _short_text(_table_value(record, "creator_name"), 14),
                _short_text(_table_value(record, "follower_count_raw"), 10),
                _short_text(_table_value(record, "total_liked_count_raw"), 10),
                _short_text(_table_value(record, "total_interaction_text"), 18),
                video_url_status,
                _short_text(_table_value(record, "comment_collection_status"), 18),
                _short_text(_table_value(record, "record_id"), 28),
            ]
        )

    widths = []
    for col_index, header in enumerate(headers):
        max_width = len(header)
        for row in rows:
            max_width = max(max_width, len(row[col_index]))
        widths.append(max_width)

    def border(left: str, middle: str, right: str) -> str:
        return left + middle.join("─" * (width + 2) for width in widths) + right

    def row_line(values: list[str]) -> str:
        cells = []
        for value, width in zip(values, widths):
            cells.append(f" {value:<{width}} ")
        return "│" + "│".join(cells) + "│"

    print("\n" + border("┌", "┬", "┐"))
    print(row_line(headers))
    print(border("├", "┼", "┤"))

    for row in rows:
        print(row_line(row))

    print(border("└", "┴", "┘") + "\n")
def _export_discovery_records_csv(records: list, output_path: Path) -> None:
    fieldnames = [
        "record_id", "creator_name", "profile_follower_count_raw",
        "profile_total_liked_count_raw", "like_count_raw",
        "comment_count_raw", "share_count_raw", "favorite_count_raw",
        "homepage_screenshot_path"
    ]
    '''
    for i in range(1, 16):
        fieldnames.append(f"recent_{i:02d}_like_count")
    '''
    for i in range(4, 16):
        fieldnames.append(f"recent_{i:02d}_like_count")

    fieldnames.extend(["video_url", "video_url_capture_source", "comment_collection_status", "description"])

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            notes = getattr(record, "notes", "") or ""

            homepage_screenshot_path = ""
            recent_works = []

            for part in notes.split("；"):
                if part.startswith("homepage_screenshot="):
                    homepage_screenshot_path = part.replace("homepage_screenshot=", "", 1)

                elif part.startswith("profile_recent_works_json="):
                    raw_json = part.replace("profile_recent_works_json=", "", 1)
                    try:
                        parsed = json.loads(raw_json)
                        if isinstance(parsed, list):
                            recent_works = parsed[:15]
                    except Exception:
                        recent_works = []

            row = {
                "record_id": getattr(record, "record_id", ""),
                "creator_name": getattr(record, "creator_name", ""),
                "profile_follower_count_raw": getattr(record, "follower_count_raw", ""),
                "profile_total_liked_count_raw": getattr(record, "total_liked_count_raw", ""),
                "like_count_raw": getattr(record, "like_count_raw", ""),
                "comment_count_raw": getattr(record, "comment_count_raw", ""),
                "share_count_raw": getattr(record, "share_count_raw", ""),
                "favorite_count_raw": getattr(record, "favorite_count_raw", ""),
                "homepage_screenshot_path": homepage_screenshot_path,
                "video_url": getattr(record, "video_url", ""),
                "video_url_capture_source": getattr(record, "video_url_capture_source", ""),
                "comment_collection_status": getattr(record, "comment_collection_status", ""),
                "description": getattr(record, "active_text_summary", "")
                or getattr(record, "expanded_description_text", "")
                or getattr(record, "video_description_raw", ""),
            }
            '''
            for i in range(1, 16):
                prefix = f"recent_{i:02d}"
                item = recent_works[i - 1] if i - 1 < len(recent_works) else {}

                row[f"{prefix}_like_count"] = item.get("like_count", "") if isinstance(item, dict) else ""
            '''

            for i in range(4, 16):
                prefix = f"recent_{i:02d}"

                # recent_04 对应 recent_works[0]
                # recent_05 对应 recent_works[1]
                # ...
                item_index = i - 4
                item = recent_works[item_index] if item_index < len(recent_works) else {}

                row[f"{prefix}_like_count"] = item.get("like_count", "") if isinstance(item, dict) else ""
   

            writer.writerow(row)

def _cycle_looks_like_feed_shell_stuck(cycle) -> bool:
    """Detect when Douyin is stuck on /jingxuan shell instead of a real active video."""
    feed_snapshot = getattr(cycle, "feed_snapshot", None)

    page_url = (
        getattr(feed_snapshot, "page_url", None)
        or getattr(cycle, "page_url", None)
        or ""
    )

    page_title = (
        getattr(feed_snapshot, "page_title", None)
        or getattr(cycle, "page_title", None)
        or ""
    )

    creator_name = (
        getattr(feed_snapshot, "creator_name", None)
        or getattr(cycle, "creator_name", None)
    )

    video_url = (
        getattr(feed_snapshot, "video_url", None)
        or getattr(cycle, "video_url", None)
    )

    active_text = (
        getattr(feed_snapshot, "active_text_summary", None)
        or getattr(feed_snapshot, "feed_identity", None)
        or getattr(cycle, "active_text_summary", None)
        or getattr(cycle, "feed_identity", None)
        or ""
    )

    homepage_open_state = getattr(cycle, "homepage_open_state", None)

    footer_hints = [
        "开启读屏标签",
        "读屏标签已关闭",
        "下载 APP",
        "京ICP备",
        "京公网安备",
        "用户服务协议",
        "隐私政策",
        "站点地图",
    ]

    has_footer_text = any(hint in active_text for hint in footer_hints)

    is_jingxuan_shell = (
        "douyin.com/jingxuan" in page_url
        or "抖音精选电脑版" in page_title
    )

    missing_real_video = not creator_name and not video_url

    f_key_failed = homepage_open_state in {
        "f_no_effect_skipped",
        "no_author_link",
        "homepage_open_failed",
        None,
    }

    return is_jingxuan_shell and missing_real_video and has_footer_text and f_key_failed


def _force_reset_recommend_feed_from_shell(adapter, debug_label: str, logger=None) -> bool:
    """Hard reset Douyin from /jingxuan shell back to a real recommend feed."""
    page = getattr(adapter, "page", None)
    if page is None:
        return False

    def _safe_log(message: str, **extra):
        if logger:
            logger.warning(
                message,
                extra={
                    "debug_label": debug_label,
                    **extra,
                },
            )

    def _looks_like_shell_page() -> bool:
        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""

        try:
            title = page.title() or ""
        except Exception:
            title = ""

        try:
            body_text = page.locator("body").inner_text(timeout=1200)
        except Exception:
            body_text = ""

        footer_hints = [
            "开启读屏标签",
            "读屏标签已关闭",
            "下载抖音精选",
            "京ICP备",
            "京公网安备",
            "用户服务协议",
            "隐私政策",
            "站点地图",
        ]

        video_hints = [
            "@",
            "听抖音",
            "倍速",
            "清屏",
            "连播",
            "评论",
            "分享",
        ]

        has_footer = any(hint in body_text for hint in footer_hints)
        has_video = any(hint in body_text for hint in video_hints)

        return (
            "douyin.com/jingxuan" in current_url
            or "抖音精选电脑版" in title
            or (has_footer and not has_video)
        )

    # 第 1 层：先尝试关闭弹窗/评论面板/浮层
    for key in ["Escape", "Escape", "ArrowDown"]:
        try:
            page.keyboard.press(key)
            page.wait_for_timeout(500)
        except Exception:
            pass

    # 第 2 层：普通跳转回推荐页
    try:
        page.goto(
            "https://www.douyin.com/?recommend=1&from_nav=1",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        page.wait_for_timeout(3500)
    except Exception as exc:
        _safe_log(
            "failed to goto recommend feed during shell reset",
            error=str(exc),
        )

    # 尝试用键盘/滚轮激活视频流
    for _ in range(4):
        try:
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(700)
        except Exception:
            pass

    for _ in range(3):
        try:
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(700)
        except Exception:
            pass

    # 如果已经离开 /jingxuan，就成功
    if not _looks_like_shell_page():
        _safe_log(
            "recommend feed hard reset from shell completed",
            recovered=True,
            page_url=page.url,
            page_title=page.title(),
        )
        return True

    # 第 3 层：普通跳转无效，强制从主页重新进入推荐
    _safe_log(
        "normal shell reset still stuck on jingxuan; trying stronger reset",
        page_url=page.url,
        page_title=page.title(),
    )

    try:
        page.goto(
            "https://www.douyin.com/",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        page.wait_for_timeout(3500)
    except Exception as exc:
        _safe_log(
            "failed to goto douyin home during stronger shell reset",
            error=str(exc),
        )

    # 尝试点击“推荐”
    recommend_texts = ["推荐", "首页", "精选"]
    for text in recommend_texts:
        try:
            locator = page.get_by_text(text, exact=True)
            if locator.count() > 0:
                locator.first.click(timeout=2000)
                page.wait_for_timeout(2500)
                break
        except Exception:
            pass

    # 再尝试键盘激活
    for _ in range(5):
        try:
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(800)
        except Exception:
            pass

    for _ in range(3):
        try:
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(800)
        except Exception:
            pass

    recovered = not _looks_like_shell_page()

    _safe_log(
        "recommend feed hard reset from shell completed",
        recovered=recovered,
        page_url=page.url,
        page_title=page.title(),
    )

    return recovered

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

            self._wait_until_login_ready_without_enter(
                adapter=adapter,
                context="bootstrap-login-gate",
                max_wait_seconds=300,
                check_interval_seconds=3,
            )

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
        xingtu_queued = 0
        observation_count = 0
        records_for_analysis: set[str] = set()
        saved_records_for_table: list[CreatorDiscoveryRecord] = []
        seen_creator_names_this_run: set[str] = set()
        seen_record_ids_this_run: set[str] = set()
        feed_shell_streak = 0
        start_time = time.monotonic()
        stalled_feed_streak = 0

        # 防止遇到直播间时 live_room_streak / last_live_room_url 未定义
        live_room_streak = 0
        last_live_room_url = None

        session_path = self._session_path()
        deadline = self._deadline_at(start_time)

        def _time_limit_reached() -> bool:
            if self.run_config.max_minutes <= 0:
                return False
            return (time.monotonic() - start_time) / 60 >= self.run_config.max_minutes

        with BrowserSession(self.browser_config, session_path) as browser:
            self._log_session_state(browser, session_path, mode="creator-discovery")
            adapter = DouyinPageAdapter(browser.page, self.artifacts, self.logger)
            adapter.open_homepage()

            self._wait_until_login_ready_without_enter(
                adapter=adapter,
                context="discovery-login-gate",
                max_wait_seconds=300,
                check_interval_seconds=3,
            )

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
                try:
                    cycle = self._browse_cycle_with_resume(
                        adapter=adapter,
                        observation_index=observation_count,
                        debug_label=debug_label,
                        deadline=deadline,
                    )
                except SearchAgentError as exc:
                    if "Captcha detected and still present after one refresh" in str(exc):
                        self.logger.warning(
                            "captcha blocked run; finishing gracefully and exporting csv",
                            extra={
                                "observation_index": observation_count,
                                "successful_records": qualified,
                                "skipped_items": skipped,
                                "error": str(exc),
                            },
                        )
                        break
                    raise
                self._log_browse_cycle(cycle)

                if _time_limit_reached():
                    self.logger.info(
                        "max_minutes reached after browse cycle; finishing gracefully",
                        extra={
                            "observation_index": observation_count,
                            "successful_records": qualified,
                            "skipped_items": skipped,
                            "max_minutes": self.run_config.max_minutes,
                        },
                    )
                    break

                if _cycle_looks_like_feed_shell_stuck(cycle):
                    skipped += 1
                    feed_shell_streak += 1

                    self.logger.warning(
                        "recommend feed shell stuck detected; skip snapshot and hard reset feed",
                        extra={
                            "observation_index": observation_count,
                            "feed_shell_streak": feed_shell_streak,
                            "page_url": getattr(adapter.page, "url", None),
                            "page_title": adapter._safe_title(),
                            "feed_identity": getattr(cycle.feed_snapshot, "feed_identity", None),
                            "creator_name": getattr(cycle.feed_snapshot, "creator_name", None),
                            "video_url": getattr(cycle.feed_snapshot, "video_url", None),
                            "homepage_open_state": getattr(cycle, "homepage_open_state", None),
                        },
                    )

                    try:
                        recovered = _force_reset_recommend_feed_from_shell(
                            adapter=adapter,
                            debug_label=f"{debug_label}_feed_shell_stuck_{feed_shell_streak}",
                            logger=self.logger,
                        )

                        if not recovered and feed_shell_streak >= 3:
                            self.logger.error(
                                "recommend feed shell recovery failed repeatedly; stop run early",
                                extra={
                                    "observation_index": observation_count,
                                    "feed_shell_streak": feed_shell_streak,
                                    "page_url": getattr(adapter.page, "url", None),
                                    "page_title": adapter._safe_title(),
                                },
                            )
                            break
                    except Exception as exc:
                        self.logger.warning(
                            "feed shell hard reset failed",
                            extra={
                                "observation_index": observation_count,
                                "feed_shell_streak": feed_shell_streak,
                                "error": str(exc),
                            },
                        )

                    continue
                else:
                    feed_shell_streak = 0
                # 这里放直播保护
                current_page_url = adapter.page.url or ""

                if "/root/live/" in current_page_url:
                    skipped += 1

                    if last_live_room_url == current_page_url:
                        live_room_streak += 1
                    else:
                        live_room_streak = 1
                        last_live_room_url = current_page_url

                    self.logger.warning(
                        "live room url detected after browse cycle; recover and force skip current area",
                        extra={
                            "observation_index": observation_count,
                            "live_room_streak": live_room_streak,
                            "page_url": current_page_url,
                            "page_title": adapter._safe_title(),
                            "feed_identity": cycle.feed_snapshot.feed_identity,
                            "creator_name": cycle.feed_snapshot.creator_name,
                        },
                    )

                    try:
                        adapter._recover_recommend_feed_if_polluted(
                            debug_label=f"{debug_label}_live_room_after_browse"
                        )
                    except Exception:
                        pass

                    # 重点：如果同一个直播连续出现，就不要只翻 1 条，直接多翻几条
                    force_skip_count = 3 if live_room_streak >= 2 else 1

                    for skip_index in range(force_skip_count):
                        try:
                            movement = self._run_with_interactive_pause(
                                adapter=adapter,
                                operation=lambda: adapter.advance_feed(
                                    cycle.feed_snapshot,
                                    debug_label=f"{debug_label}_post_live_recover_{skip_index + 1}",
                                ),
                                context=f"feed-scroll-live-recover:{debug_label}:{skip_index + 1}",
                                deadline=deadline,
                            )
                            self._log_feed_progression(movement, observation_count)
                        except Exception as exc:
                            self.logger.warning(
                                "failed to force skip after live room",
                                extra={
                                    "observation_index": observation_count,
                                    "skip_index": skip_index + 1,
                                    "error": str(exc),
                                },
                            )
                            break

                        try:
                            if "/root/live/" not in (adapter.page.url or ""):
                                # 给页面一点时间稳定
                                adapter.page.wait_for_timeout(600)
                        except Exception:
                            pass

                    continue
                else:
                    live_room_streak = 0
                    last_live_room_url = None

                # 新增：直播内容和商品卡视频直接跳过，不保存 discovery record，不抓评论，不进 content analysis queue
                if (cycle.feed_snapshot.is_live or cycle.homepage_open_state in {"live_skipped", "commerce_skipped"}):
                    skipped += 1
                    skip_reason = (
                        "commerce"
                        if cycle.homepage_open_state == "commerce_skipped"
                        else "live"
                    )

                    skip_message = (
                        "commerce feed item skipped before content snapshot"
                        if skip_reason == "commerce"
                        else "live feed item skipped before content snapshot"
                    )

                    self.logger.info(
                        skip_message,
                        extra={
                            "observation_index": cycle.observation_index,
                            "creator_name": cycle.feed_snapshot.creator_name,
                            "feed_identity": cycle.feed_snapshot.feed_identity,
                            "active_text_summary": cycle.feed_snapshot.active_text_summary,
                            "homepage_open_state": cycle.homepage_open_state,
                            "homepage_close_state": cycle.homepage_close_state,
                            "skip_reason": skip_reason,
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
                        live_room_streak = 0
                        last_live_room_url = None
                        continue

                    stalled_feed_streak += 1
                    if stalled_feed_streak >= self.STALLED_FEED_LIMIT:
                        exc = self._build_feed_debug_exception(
                            cycle.feed_snapshot,
                            message="跳过直播内容后滚动未进入下一条视频，当前推荐流停滞。",
                            movement=movement,
                        )
                        if self._handle_resumable_pause(adapter, exc, context="stalled-feed-after-live-skip", deadline=deadline):
                            stalled_feed_streak = 0
                            continue
                        raise exc

                    continue

                minimal_record = self._build_discovery_record(cycle)

                minimal_creator_key = (minimal_record.creator_name or "").strip().lower()
                minimal_record_key = (minimal_record.record_id or "").strip().lower()

                is_duplicate_this_run = False
                duplicate_reason = None

                if minimal_creator_key and minimal_creator_key in seen_creator_names_this_run:
                    is_duplicate_this_run = True
                    duplicate_reason = "本轮重复达人"

                if minimal_record_key and minimal_record_key in seen_record_ids_this_run:
                    is_duplicate_this_run = True
                    duplicate_reason = "本轮重复 record_id"

                if is_duplicate_this_run:
                    skipped += 1
                    self.logger.info(
                        "discovery record skipped as duplicate in current run",
                        extra={
                            "record_id": minimal_record.record_id,
                            "creator_name": minimal_record.creator_name,
                            "reason": duplicate_reason,
                        },
                    )
                else:
                    if _time_limit_reached():
                        self.logger.info(
                            "max_minutes reached before content snapshot; finishing gracefully",
                            extra={
                                "observation_index": observation_count,
                                "successful_records": qualified,
                                "skipped_items": skipped,
                                "max_minutes": self.run_config.max_minutes,
                            },
                        )
                        break

                    try:
                        content_snapshot = self._collect_content_snapshot_with_resume(
                            adapter=adapter,
                            candidate=cycle.feed_snapshot,
                            debug_label=debug_label,
                            deadline=deadline,
                        )
                    except OSError as exc:
                        if getattr(exc, "errno", None) == 28:
                            skipped += 1
                            self.logger.warning(
                                "disk space is full during content snapshot; skip current record",
                                extra={
                                    "observation_index": observation_count,
                                    "debug_label": debug_label,
                                    "error": str(exc),
                                },
                            )
                            continue
                        raise
                    except Exception as exc:
                        skipped += 1
                        self.logger.warning(
                            "content snapshot failed; skip current record",
                            extra={
                                "observation_index": observation_count,
                                "debug_label": debug_label,
                                "error": str(exc),
                            },
                        )
                        continue

                    if _snapshot_is_polluted(content_snapshot):
                        skipped += 1
                        self.logger.warning(
                            "polluted page snapshot skipped before saving record",
                            extra={
                                "observation_index": observation_count,
                                "creator_name": getattr(content_snapshot, "creator_name", None),
                                "video_url": getattr(content_snapshot, "video_url", None),
                                "video_url_capture_source": getattr(content_snapshot, "video_url_capture_source", None),
                                "active_text_summary": getattr(content_snapshot, "active_text_summary", None),
                                "expanded_description_text": getattr(content_snapshot, "expanded_description_text", None),
                                "page_url": getattr(content_snapshot, "page_url", None),
                                "page_title": getattr(content_snapshot, "page_title", None),
                            },
                        )

                        try:
                            adapter._recover_recommend_feed_if_polluted(
                                debug_label=f"{debug_label}_polluted_before_save"
                            )
                        except Exception:
                            pass

                        continue

                    if (
                        not getattr(content_snapshot, "video_url", None)
                        and getattr(content_snapshot, "comment_collection_status", None) == "panel_open_failed"
                    ):
                        skipped += 1
                        self.logger.warning(
                            "snapshot skipped because video_url missing and comment panel failed; force advance feed",
                            extra={
                                "observation_index": observation_count,
                                "creator_name": getattr(content_snapshot, "creator_name", None),
                                "comment_collection_status": getattr(content_snapshot, "comment_collection_status", None),
                                "active_text_summary": getattr(content_snapshot, "active_text_summary", None),
                            },
                        )

                        try:
                            movement = self._run_with_interactive_pause(
                                adapter=adapter,
                                operation=lambda: adapter.advance_feed(
                                    content_snapshot,
                                    debug_label=f"{debug_label}_post_missing_url_panel_failed",
                                ),
                                context=f"feed-scroll-missing-url-panel-failed:{debug_label}",
                                deadline=deadline,
                            )
                            self._log_feed_progression(movement, observation_count)

                            if not movement.changed:
                                self.logger.warning(
                                    "force advance after missing video_url failed",
                                    extra={
                                        "observation_index": observation_count,
                                        "creator_name": getattr(content_snapshot, "creator_name", None),
                                        "debug_label": debug_label,
                                        "page_url": getattr(adapter.page, "url", None),
                                        "page_title": adapter._safe_title(),
                                    },
                                )
                        except Exception as exc:
                            self.logger.warning(
                                "failed to force advance after missing video_url and panel_open_failed",
                                extra={
                                    "observation_index": observation_count,
                                    "creator_name": getattr(content_snapshot, "creator_name", None),
                                    "error": str(exc),
                                },
                            )

                        continue

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

                    record_creator_key = (record.creator_name or "").strip().lower()
                    record_key = (record.record_id or "").strip().lower()

                    try:
                        self.discovery_store.append(record)
                    except OSError as exc:
                        if getattr(exc, "errno", None) == 28:
                            skipped += 1
                            self.logger.warning(
                                "disk space is full while saving discovery record; skip current record",
                                extra={
                                    "record_id": record.record_id,
                                    "creator_name": record.creator_name,
                                    "error": str(exc),
                                },
                            )
                            continue
                        raise

                    existing_records.append(record)
                    saved_records_for_table.append(record)

                    if record_creator_key:
                        seen_creator_names_this_run.add(record_creator_key)

                    if record_key:
                        seen_record_ids_this_run.add(record_key)

                    if self.run_config.content_analysis_enabled:
                        self.analysis_queue_store.enqueue(record)
                        records_for_analysis.add(record.record_id)
                    if self._enqueue_record_for_xingtu(record):
                        xingtu_queued += 1
                    qualified += 1
                    _print_discovery_record_to_terminal(record)

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

                    if _time_limit_reached():
                        self.logger.info(
                            "max_minutes reached after saving record; finishing gracefully",
                            extra={
                                "observation_index": observation_count,
                                "successful_records": qualified,
                                "skipped_items": skipped,
                                "max_minutes": self.run_config.max_minutes,
                            },
                        )
                        break

                self.logger.info(
                    "scrolling to next video",
                    extra={
                        "observation_index": observation_count,
                        "feed_identity": cycle.feed_snapshot.feed_identity,
                        "page_url": cycle.feed_snapshot.page_url,
                        "page_title": cycle.feed_snapshot.page_title,
                    },
                )

                try:
                    adapter._recover_recommend_feed_if_polluted(
                        debug_label=f"{debug_label}_before_scroll"
                    )
                except Exception:
                    pass

                try:
                    movement = self._run_with_interactive_pause(
                        adapter=adapter,
                        operation=lambda: adapter.advance_feed(cycle.feed_snapshot, debug_label=f"{debug_label}_post"),
                        context=f"feed-scroll:{debug_label}",
                        deadline=deadline,
                    )
                    self._log_feed_progression(movement, observation_count)

                except SearchAgentError as exc:
                    if "Douyin workflow timed out while waiting for manual recovery" in str(exc):
                        self.logger.info(
                            "workflow deadline reached after saving record; finishing gracefully",
                            extra={
                                "observation_index": observation_count,
                                "successful_records": qualified,
                                "skipped_items": skipped,
                                "context": f"feed-scroll:{debug_label}",
                            },
                        )
                        break
                    raise
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
        _print_discovery_records_table(saved_records_for_table)

        summary_csv_path = self.paths.discovery_output.with_name(
            f"discovery_summary_{self.artifacts.run_id}.csv"
        )

        _export_discovery_records_csv(saved_records_for_table, summary_csv_path)

        self.logger.info(
            "discovery csv summary exported",
            extra={
                "csv_path": str(summary_csv_path),
                "record_count": len(saved_records_for_table),
            },
        )

        return RunSummary(
            stage=WorkflowStage.CREATOR_DISCOVERY,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=qualified,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=xingtu_queued,
            output_path=str(self.paths.discovery_output),
            queue_path=str(self.paths.queue_output),
        )

    def _enqueue_record_for_xingtu(self, record: CreatorDiscoveryRecord) -> bool:
        if not record.is_ready_for_xingtu():
            self.logger.info(
                "discovery record not queued for Xingtu because required fields are incomplete",
                extra={
                    "record_id": record.record_id,
                    "creator_name": record.creator_name,
                    "video_url": record.video_url,
                    "collection_date": record.collection_date,
                    "total_interaction_text": record.total_interaction_text,
                    "follower_count_raw": record.follower_count_raw,
                    "has_content_tags": bool(record.content_leaf_tags or record.content_taxonomy_path),
                },
            )
            return False
        queue_payload = record.model_dump(mode="json")
        queue_payload.update(
            {
                "status": RecordStatus.QUEUED_FOR_XINGTU.value,
                "next_action": NextAction.QUEUE_FOR_XINGTU.value,
            }
        )
        self.queue_store.enqueue(CreatorDiscoveryRecord.model_validate(queue_payload))
        self.logger.info(
            "discovery record queued for Xingtu enrichment",
            extra={"record_id": record.record_id, "creator_name": record.creator_name, "queue_path": str(self.paths.queue_output)},
        )
        return True
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
    def _pause_if_login_or_verification_required(
    self,
    adapter: DouyinPageAdapter,
    context: str,
    ) -> None:
        """打开抖音后先检查登录状态。

        如果当前页面是：
        - 未登录
        - 登录弹窗
        - 扫码登录
        - 手机号登录
        - 验证码 / 滑块 / 人机验证

        就停在当前页面，不刷新、不跳转、不继续抓取。
        用户手动完成登录后，在终端按 Enter，程序再继续。
        """
        login_states = {
            "unauthenticated",
            "login_modal",
            "captcha_blocked",
        }

        while True:
            snapshot = adapter.classify_page_state(
                debug_label=f"{context}_login_gate",
                capture=True,
            )

            if snapshot.state not in login_states:
                return

            exc = adapter._snapshot_to_blocking_error(
                snapshot,
                page_name=context,
            )

            self.logger.warning(
                "douyin login gate paused; waiting for manual login or verification",
                extra={
                    "context": context,
                    "page_state": snapshot.state,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "reason": snapshot.reason,
                    "detected_phrase": snapshot.detected_phrase,
                    "screenshot_path": snapshot.screenshot_path,
                    "browser_will_remain_open": True,
                },
            )

            if not self._handle_resumable_pause(
                adapter=adapter,
                exc=exc,
                context=context,
                deadline=None,
            ):
                raise exc
    def _wait_until_login_ready_without_enter(
    self,
    adapter: DouyinPageAdapter,
    context: str,
    max_wait_seconds: int = 300,
    check_interval_seconds: int = 3,
    ) -> None:
        """自动等待抖音登录/验证完成，不需要用户回终端按 Enter。

        逻辑：
        1. 如果当前是未登录/登录弹窗/验证码，就停在当前页面。
        2. 每隔几秒自动检查一次页面状态。
        3. 一旦检测到已经不是登录/验证码状态，就自动进入推荐流。
        """
        login_states = {
            "unauthenticated",
            "login_modal",
            "captcha_blocked",
        }

        start_wait = time.monotonic()

        while True:
            snapshot = adapter.classify_page_state(
                debug_label=f"{context}_auto_login_gate",
                capture=True,
            )

            self.logger.info(
                "douyin auto login gate check",
                extra={
                    "context": context,
                    "page_state": snapshot.state,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "reason": snapshot.reason,
                    "detected_phrase": snapshot.detected_phrase,
                },
            )

            # 已经不在登录/验证码状态了
            if snapshot.state not in login_states:
                current_url = snapshot.page_url or ""

                # 如果登录后停在 /jingxuan，就主动进推荐流
                if "/jingxuan" in current_url:
                    adapter.enter_recommend_feed_from_jingxuan()

                return

            # 超时保护，避免永远卡住
            elapsed = time.monotonic() - start_wait
            if elapsed >= max_wait_seconds:
                raise SearchAgentError(
                    f"Douyin login/verification was not completed within {max_wait_seconds} seconds: {context}"
                )

            print(
                f"\nDouyin 正在等待你完成登录/验证码，不需要按 Enter。"
                f"\n当前状态: {snapshot.state}"
                f"\n原因: {snapshot.reason}"
                f"\n程序会在 {check_interval_seconds} 秒后自动重新检查...\n",
                flush=True,
            )

            try:
                adapter.page.wait_for_timeout(check_interval_seconds * 1000)
            except Exception:
                time.sleep(check_interval_seconds)      

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
                        "douyin retry succeeded after login/verification recovery",  
                        extra={"context": context, "browser_will_remain_open": True},
                    )
                return result
            except BlockingStateError as exc:
                if getattr(exc, "page_state", None) in {
                    "unauthenticated",
                    "login_modal",
                    "captcha_blocked",
                }:
                    self._wait_until_login_ready_without_enter(
                        adapter=adapter,
                        context=context,
                        max_wait_seconds=300,
                        check_interval_seconds=3,
                    )
                    paused_once = True
                    continue

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
        safe_recent_video_titles = [
            str(title)
            for title in (profile.recent_video_titles if profile else [])
            if title is not None and str(title).strip()
        ]
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
                recent_videos_summary=safe_recent_video_titles,
                visible_subtitle_segments=candidate.visible_subtitle_segments,
                top_comments=candidate.top_comments,
                visible_scenes=profile.visible_scenes if profile else [],
                speaking_style=profile.speaking_style if profile else None,
                video_duration_pattern=profile.video_duration_pattern if profile else None,
                ai_generated_flag=candidate.ai_generated_flag,
                extra_notes=profile_bio,
            )
        )
        recent_works = []

        if profile:
            recent_video_like_raws = getattr(profile, "recent_video_like_raws", []) or []

            for like_raw in recent_video_like_raws[:15]:
                if like_raw is None:
                    continue

                like_text = str(like_raw).strip()
                if not like_text:
                    continue

                recent_works.append({
                    "index": len(recent_works) + 1,
                    "like_count": like_text,
                })

                if len(recent_works) >= 15:
                    break

        recent_works_json = json.dumps(
            recent_works,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        notes = "；".join(
            part
            for part in [
                "内容快照已采集",
                f"homepage_screenshot={cycle.homepage_screenshot_path}" if cycle.homepage_screenshot_path else None,
                f"profile_recent_works_json={recent_works_json}" if recent_works else None,
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
            recent_video_titles=safe_recent_video_titles,
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
