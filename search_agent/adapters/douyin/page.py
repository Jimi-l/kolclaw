from __future__ import annotations

import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field, replace
from urllib.parse import parse_qs, urljoin, urlparse

from search_agent.artifacts import ArtifactManager
from search_agent.browser.page_utils import body_text, first_attribute, first_text, first_visible_locator, locator_text, page_contains_any_text
from search_agent.enums import BlockReason
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError
from search_agent.models.common import CommentSnippet

from . import selectors


@dataclass(slots=True)
class FeedCandidateSnapshot:
    creator_name: str | None = None
    creator_profile_url: str | None = None
    video_url: str | None = None
    video_url_capture_source: str | None = None
    publish_time_raw: str | None = None
    total_interaction_text: str | None = None
    like_count_raw: str | None = None
    comment_count_raw: str | None = None
    favorite_count_raw: str | None = None
    share_count_raw: str | None = None
    ai_generated_flag: bool | None = None
    is_live: bool = False
    is_commerce: bool = False #
    is_ad: bool = False
    caption_text: str | None = None
    raw_text: str | None = None
    video_title_text: str | None = None
    video_description_raw: str | None = None
    expanded_description_text: str | None = None
    video_text_bundle: str | None = None
    chapter_texts: list[str] = field(default_factory=list)
    related_search_terms: list[str] = field(default_factory=list)
    author_statement_texts: list[str] = field(default_factory=list)
    visible_subtitle_segments: list[str] = field(default_factory=list)
    top_comments: list[CommentSnippet] = field(default_factory=list)
    top_comments_source: str | None = None
    comment_collection_status: str | None = None
    comment_collection_debug: str | None = None
    keyframe_paths: list[str] = field(default_factory=list)
    feed_selector_hint: str | None = None
    feed_identity: str | None = None
    active_text_summary: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    pre_extract_screenshot_path: str | None = None


@dataclass(slots=True)
class FeedAdvanceResult:
    changed: bool
    before_identity: str | None = None
    after_identity: str | None = None
    before_summary: str | None = None
    after_summary: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    screenshot_path: str | None = None
    debug_label: str | None = None


@dataclass(slots=True)
class PageStateSnapshot:
    state: str
    page_url: str | None = None
    page_title: str | None = None
    visible_text_summary: str | None = None
    detected_phrase: str | None = None
    reason: str | None = None
    screenshot_path: str | None = None
    blocking_reason: BlockReason | None = None
    missing_readiness_anchors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HomepageBrowseResult:
    observation_index: int
    feed_snapshot: FeedCandidateSnapshot
    profile_snapshot: ProfileAnalysisSnapshot | None = None
    homepage_screenshot_path: str | None = None
    homepage_page_url: str | None = None
    homepage_page_title: str | None = None
    homepage_open_state: str | None = None
    homepage_close_state: str | None = None


@dataclass(slots=True)
class CommentCollectionResult:
    comments: list[CommentSnippet] = field(default_factory=list)
    source: str = "none"
    status: str = "panel_open_failed"
    debug: str | None = None
    network_count: int = 0
    ui_count: int = 0
    panel_visible: bool = False
    network_url: str | None = None


@dataclass(slots=True)
class ProfileVideoCard:
    url: str | None
    title: str | None
    like_raw: str | None
    publish_time_raw: str | None = None
    publish_timestamp: int | None = None
    is_pinned: bool = False


@dataclass(slots=True)
class ProfileAnalysisSnapshot:
    creator_name: str | None = None
    follower_count_raw: str | None = None
    total_liked_count_raw: str | None = None
    profile_bio: str | None = None
    recommendation_video_position: str | None = None
    recommendation_video_like_raw: str | None = None
    recent_video_like_raws: list[str | None] = field(default_factory=list)
    recent_video_titles: list[str] = field(default_factory=list)
    visible_scenes: list[str] = field(default_factory=list)
    speaking_style: str | None = None
    video_duration_pattern: str | None = None
    notes: list[str] = field(default_factory=list)
    recent_video_publish_times: list[str | None] = field(default_factory=list)
    recent_video_urls: list[str | None] = field(default_factory=list)

def _compact_profile_video_cards(
    cards: list[ProfileVideoCard],
    limit: int = 15,
    total_liked_count_raw: str | None = None,
) -> list[ProfileVideoCard]:
    """Clean profile video cards before saving to CSV.

    作用：
    1. 去掉空点赞量
    2. 去掉主页头部误抓的数据，比如粉丝/总获赞/关注
    3. 去掉 DOM 嵌套造成的连续重复
    4. 尽量保留真实不同作品的相同点赞数
    """
    cleaned: list[ProfileVideoCard] = []
    seen_urls: set[str] = set()
    previous_no_url_key: str | None = None

    def normalize_metric(value: str | None) -> str:
        if not value:
            return ""
        return (
            str(value)
            .replace(" ", "")
            .replace("\n", "")
            .replace("\t", "")
            .replace("W", "w")
            .replace("K", "k")
            .strip()
        )

    def normalize_title(value: str | None) -> str:
        if not value:
            return ""
        text = str(value).replace("\n", " ").replace("\t", " ").strip()
        text = text.replace("播放中", "").strip()
        text = re.sub(r"\s+", " ", text)
        return text[:80]

    total_liked_key = normalize_metric(total_liked_count_raw)

    for card in cards or []:
        if card is None:
            continue

        like_raw = normalize_metric(card.like_raw)
        title = normalize_title(card.title)
        url = (card.url or "").strip()

        # 1. 没有点赞量的不要，避免 recent_03_like_count 为空
        if not like_raw:
            continue

        # 2. 点赞量必须像数字：551、2.1万、10万、1.3亿
        if not re.fullmatch(r"\d+(?:\.\d+)?(?:万|亿|w|W|k|K)?", like_raw):
            continue

        combined_text = f"{title} {like_raw}"

        # 3. 过滤主页头部信息
        if (
            "粉丝" in combined_text
            and "获赞" in combined_text
            and "关注" in combined_text
        ):
            continue

        if "TA的作品" in combined_text:
            continue

        if "详情" in combined_text and "评论" in combined_text:
            continue

        # 4. 如果没有作品 url / title，而且点赞量刚好等于主页总获赞，
        # 大概率是把主页头部“总获赞”误当成作品点赞了。
        if not url and not title and total_liked_key and like_raw == total_liked_key:
            continue

        # 5. 有 URL 时按 URL 去重
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            previous_no_url_key = None
        else:
            # 6. 没有 URL 时，只去掉“连续重复”的同一个 DOM 嵌套结果
            # 不做全局 like_raw 去重，避免误删真实不同作品刚好点赞数一样的情况。
            no_url_key = f"{like_raw}|{title}"

            if no_url_key == previous_no_url_key:
                continue

            previous_no_url_key = no_url_key

        cleaned.append(card)

        if len(cleaned) >= limit:
            break

    return cleaned

class DouyinPageAdapter:
    LOGIN_BLOCK_REASONS = {
        BlockReason.LOGIN_REQUIRED,
        BlockReason.QR_LOGIN_REQUIRED,
        BlockReason.SMS_LOGIN_REQUIRED,
        BlockReason.SESSION_EXPIRED,
    }
    RESUMABLE_BLOCK_REASONS = LOGIN_BLOCK_REASONS | {
        BlockReason.CAPTCHA_BLOCKED,
        BlockReason.EXTERNAL_APP_INTERRUPTION,
    }

    def __init__(self, page, artifacts: ArtifactManager, logger: logging.Logger):
        self.page = page
        self.artifacts = artifacts
        self.logger = logger
        self._jingxuan_recommend_blocked = False
        self._jingxuan_recommend_block_reason: str | None = None
        self._jingxuan_recommend_selected = False
        self._recent_aweme_items: list[dict] = []
        self._recent_comments_by_video_id: dict[str, list[CommentSnippet]] = {}
        self._recent_comment_meta_by_video_id: dict[str, dict[str, str | float | int | None]] = {}
        self._response_listener_registered = False
        self._register_response_listener()

    def _register_response_listener(self) -> None:
        if self._response_listener_registered:
            return
        try:
            self.page.on("response", self._handle_response)
            self._response_listener_registered = True
        except Exception as exc:
            self.logger.warning("Unable to register Douyin response listener: %s", exc)

    def _handle_response(self, response) -> None:
        response_url = (getattr(response, "url", "") or "").strip()
        url = response_url.lower()
        if not url:
            return
        if not any(
            token in url
            for token in (
                "aweme",
                "comment",
                "feed",
                "post",
                "recommend",
            )
        ):
            return
        try:
            headers = response.headers or {}
        except Exception:
            headers = {}
        content_type = (headers.get("content-type") or headers.get("Content-Type") or "").lower()
        if "json" not in content_type and not any(token in url for token in ("aweme", "comment", "feed")):
            return
        payload = self._read_response_payload(response)
        if not isinstance(payload, (dict, list)):
            return
        if "comment" in url:
            self._remember_comment_payload(payload, response_url=response_url)
            return
        self._remember_aweme_payload(payload)

    def _read_response_payload(self, response):
        try:
            return response.json()
        except BaseException as exc:
            if _is_target_closed_error(exc) or "cancelled" in str(exc).lower():
                return None
            try:
                body = response.text()
            except BaseException as body_exc:
                if _is_target_closed_error(body_exc) or "cancelled" in str(body_exc).lower():
                    return None
                return None
            try:
                return json.loads(body)
            except Exception:
                return None

    def open_homepage(self) -> None:
        self._ensure_page_open(goto_base=False, reason="open_homepage")
        navigation_error: Exception | None = None
        try:
            self.page.goto(
                selectors.BASE_URL,
                wait_until="domcontentloaded",
                timeout=45_000,
            )
        except Exception as exc:
            navigation_error = exc
            self.logger.warning("Douyin homepage goto did not fully stabilize: %s", exc)

        self._wait_for_timeout_safe(1_500, reason="open_homepage_stabilize")
        snapshot = self.classify_page_state()
        self.logger.info(
            "douyin root opened",
            extra={
                "page_state": snapshot.state,
                "page_url": snapshot.page_url,
                "page_title": snapshot.page_title,
                "reason": snapshot.reason,
                "detected_phrase": snapshot.detected_phrase,
            },
        )
        if navigation_error is not None:
            self.logger.info("Douyin homepage accepted through bootstrap/root checks")

    def _homepage_ready(self) -> bool:
        if first_visible_locator(self.page, selectors.HOME_READY_SELECTORS, timeout_ms=1_200) is not None:
            return True
        if self._extract_active_feed_state() is not None:
            return True

        if not self._body_is_visible():
            return False

        current_url = (self.page.url or "").lower()
        title = (self._safe_title() or "").lower()
        body = body_text(self.page, timeout_ms=1_200).strip()

        return bool(
            "douyin.com" in current_url
            or "抖音" in title
            or "douyin" in title
            or len(body) >= 20
        )

    def _body_is_visible(self) -> bool:
        try:
            return self.page.locator("body").first.is_visible(timeout=1_200)
        except Exception:
            return False

    def _safe_title(self) -> str | None:
        if not self._ensure_page_open(goto_base=False, reason="safe_title"):
            return None
        try:
            title = self.page.title()
            return title.strip() or None
        except Exception:
            return None

    def raise_for_blockers(self, page_name: str) -> None:
        snapshot = self.classify_page_state()
        if snapshot.state in {
            "captcha_blocked",
            "unauthenticated",
            "login_modal",
            "abnormal/footer/download_page",
            "live_room_open",
            "public_feed",
            "recommend_feed_shell",
            "public_jingxuan_landing",
            "jingxuan_blocked_by_external_app_prompt",
            "jingxuan_ready_to_enter_recommend",
            "visual_feed_unstable",
        }:
            raise self._snapshot_to_blocking_error(snapshot, page_name=page_name)
        if phrase := page_contains_any_text(self.page, selectors.CAPTCHA_HINTS):
            screenshot = self._capture(f"{page_name}_captcha")
            raise BlockingStateError(
                reason=BlockReason.CAPTCHA_BLOCKED,
                message=f"检测到抖音验证码/人机验证提示：{phrase}",
                page_name=page_name,
                page_state="captcha_blocked",
                screenshot_path=screenshot,
                required_user_action="Please complete the captcha or slider verification in this browser session and then rerun.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.SESSION_EXPIRED_HINTS):
            screenshot = self._capture(f"{page_name}_session_expired")
            raise BlockingStateError(
                reason=BlockReason.SESSION_EXPIRED,
                message=f"检测到抖音会话失效提示：{phrase}",
                page_name=page_name,
                page_state="unauthenticated",
                screenshot_path=screenshot,
                required_user_action="Please log into Douyin again in this browser session and tell me when it is done.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.QR_LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_qr_login")
            raise BlockingStateError(
                reason=BlockReason.QR_LOGIN_REQUIRED,
                message=f"当前抖音页面需要扫码登录：{phrase}",
                page_name=page_name,
                page_state="login_modal",
                screenshot_path=screenshot,
                required_user_action="Please scan the QR code and finish Douyin login in this browser session.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.SMS_LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_sms_login")
            raise BlockingStateError(
                reason=BlockReason.SMS_LOGIN_REQUIRED,
                message=f"当前抖音页面需要短信/手机号登录：{phrase}",
                page_name=page_name,
                page_state="login_modal",
                screenshot_path=screenshot,
                required_user_action="Please complete the SMS login flow in this browser session.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_login")
            raise BlockingStateError(
                reason=BlockReason.LOGIN_REQUIRED,
                message=f"当前抖音页面需要登录：{phrase}",
                page_name=page_name,
                page_state="unauthenticated",
                screenshot_path=screenshot,
                required_user_action="Please log into Douyin in this browser session and tell me when it is done.",
                resumable=True,
            )

    def classify_page_state(self, debug_label: str | None = None, capture: bool = False) -> PageStateSnapshot:
        if not self._ensure_page_open(goto_base=True, reason="classify_page_state"):
            return PageStateSnapshot(
                state="abnormal/footer/download_page",
                page_url=None,
                page_title=None,
                visible_text_summary=None,
                reason="Douyin 页面已关闭且暂未恢复，当前无法判断推荐流状态",
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=["active_feed_item", "creator_name", "creator_anchor", "video_anchor", "interaction_metric"],
            )
        current_url = self.page.url
        current_title = self._safe_title()
        text = body_text(self.page, timeout_ms=1_000)
        summary = _summarize_text(text, limit=260)
        active_feed = self._extract_active_feed_state()
        looks_like_feed = self._looks_like_feed_surface(text, active_feed)
        missing_anchors, readiness_details = self._inspect_feed_readiness(active_feed, text)
        readiness_reason = self._build_readiness_reason(missing_anchors, readiness_details)
        lower_url = (current_url or "").lower()
        on_jingxuan = "/jingxuan" in lower_url
        recommend_route = self._is_recommend_route(current_url)
        recommend_ready = self._find_jingxuan_recommend_target(timeout_ms=250) is not None if on_jingxuan else False
        live_room_phrase = self._detect_live_room_phrase(current_url, text, looks_like_feed)

        phrase = page_contains_any_text(self.page, selectors.CAPTCHA_HINTS)
        if phrase:
            screenshot = self._capture(
                f"douyin_captcha_{debug_label}" if capture and debug_label else "douyin_captcha"
            ) if capture else None
            return PageStateSnapshot(
                state="captcha_blocked",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=phrase,
                reason=f"检测到验证码/人机验证：{phrase}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.CAPTCHA_BLOCKED,
                missing_readiness_anchors=missing_anchors,
            )

        phrase = page_contains_any_text(self.page, selectors.QR_LOGIN_HINTS) or page_contains_any_text(self.page, selectors.SMS_LOGIN_HINTS)
        if phrase:
            screenshot = self._capture(
                f"douyin_login_modal_{debug_label}" if capture and debug_label else "douyin_login_modal"
            ) if capture else None
            return PageStateSnapshot(
                state="login_modal",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=phrase,
                reason=f"检测到登录弹层/登录流程：{phrase}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.LOGIN_REQUIRED,
                missing_readiness_anchors=missing_anchors,
            )

        phrase = page_contains_any_text(self.page, selectors.LOGIN_HINTS)
        if phrase:
            screenshot = self._capture(
                f"douyin_unauthenticated_{debug_label}" if capture and debug_label else "douyin_unauthenticated"
            ) if capture else None
            return PageStateSnapshot(
                state="unauthenticated",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=phrase,
                reason=f"当前页面未登录：{phrase}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.LOGIN_REQUIRED,
                missing_readiness_anchors=missing_anchors,
            )

        if live_room_phrase:
            screenshot = self._capture(
                f"douyin_live_room_{debug_label}" if capture and debug_label else "douyin_live_room"
            ) if capture else None
            return PageStateSnapshot(
                state="live_room_open",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=live_room_phrase,
                reason=f"当前页面进入直播间/直播态：{live_room_phrase}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if self._looks_like_self_profile(current_url):
            screenshot = self._capture(
                f"douyin_self_profile_{debug_label}" if capture and debug_label else "douyin_self_profile"
            ) if capture else None
            return PageStateSnapshot(
                state="self_profile_open",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                reason="当前页面误入我的主页，不是推荐视频作者主页。",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        external_app_phrase = page_contains_any_text(self.page, selectors.EXTERNAL_APP_HINTS)
        if external_app_phrase and not on_jingxuan and not recommend_route:
            screenshot = self._capture(
                f"douyin_external_app_{debug_label}" if capture and debug_label else "douyin_external_app"
            ) if capture else None
            return PageStateSnapshot(
                state="abnormal/footer/download_page",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=external_app_phrase,
                reason=f"检测到外部应用/打开抖音中断：{external_app_phrase}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.EXTERNAL_APP_INTERRUPTION,
                missing_readiness_anchors=missing_anchors,
            )

        download_phrase = page_contains_any_text(self.page, selectors.DOWNLOAD_PAGE_HINTS)
        if download_phrase and not on_jingxuan and not recommend_route:
            screenshot = self._capture(
                f"douyin_download_page_{debug_label}" if capture and debug_label else "douyin_download_page"
            ) if capture else None
            return PageStateSnapshot(
                state="abnormal/footer/download_page",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                detected_phrase=download_phrase,
                reason=f"检测到下载/跳 App 页面文案：{download_phrase}，但缺少足够证据将其判定为浏览器原生外部应用中断。",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if self._looks_like_profile():
            screenshot = self._capture(
                f"douyin_creator_homepage_{debug_label}" if capture and debug_label else "douyin_creator_homepage"
            ) if capture else None
            return PageStateSnapshot(
                state="creator_homepage_open",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                reason="当前页面已进入达人主页/创作者主页态。",
                screenshot_path=screenshot,
            )

        if on_jingxuan and self._jingxuan_recommend_blocked:
            screenshot = self._capture(
                f"douyin_jingxuan_open_app_block_{debug_label}" if capture and debug_label else "douyin_jingxuan_open_app_block"
            ) if capture else None
            return PageStateSnapshot(
                state="jingxuan_blocked_by_external_app_prompt",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text((active_feed or {}).get("active_text")) or summary,
                reason=self._jingxuan_recommend_block_reason or "点击 jingxuan 左侧推荐后页面未推进，推测被浏览器原生 open-app / xdg-open 提示打断。",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.EXTERNAL_APP_INTERRUPTION,
                missing_readiness_anchors=missing_anchors,
            )

        feed_interactable = self._feed_is_interactable(active_feed)
        shell_ready = self._minimal_feed_shell_ready(active_feed, text)
        recommend_route = recommend_route or self._jingxuan_recommend_selected

        if recommend_route and active_feed is not None and not missing_anchors:
            self._clear_jingxuan_recommend_block()
            return PageStateSnapshot(
                state="recommended_feed_ready",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text(active_feed.get("active_text")),
                reason="当前推荐流激活卡片已稳定，且 richer anchors 齐全，可进入后续提取。",
            )

        if recommend_route and (feed_interactable or shell_ready):
            screenshot = self._capture(
                f"douyin_recommend_feed_interactable_{debug_label}" if capture and debug_label else "douyin_recommend_feed_interactable"
            ) if capture else None
            return PageStateSnapshot(
                state="recommend_feed_interactable",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text((active_feed or {}).get("active_text")) or summary,
                reason=(
                    "推荐流已可交互，可执行 F 键主页切换与下一条切换。"
                    if shell_ready and not feed_interactable
                    else f"推荐流已可交互，已识别当前激活视频区域，可执行 F 键主页切换。{readiness_reason}"
                ),
                screenshot_path=screenshot,
                missing_readiness_anchors=missing_anchors,
            )

        if recommend_route and (active_feed is not None or looks_like_feed):
            screenshot = self._capture(
                f"douyin_recommend_feed_shell_{debug_label}" if capture and debug_label else "douyin_recommend_feed_shell"
            ) if capture else None
            return PageStateSnapshot(
                state="recommend_feed_shell",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text((active_feed or {}).get("active_text")) or summary,
                reason=(
                    "推荐页已到达，但当前仅识别到 feed shell，仍在等待激活卡片稳定。"
                    + (
                        f" 页面存在常见下载/安装文案 {download_phrase}，在 recommend 路由中仅视作普通页面文案，不单独判定为下载/异常页。"
                        if download_phrase
                        else ""
                    )
                    + f" {readiness_reason}"
                ),
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if on_jingxuan and recommend_ready:
            screenshot = self._capture(
                f"douyin_jingxuan_ready_{debug_label}" if capture and debug_label else "douyin_jingxuan_ready"
            ) if capture else None
            return PageStateSnapshot(
                state="jingxuan_ready_to_enter_recommend",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text((active_feed or {}).get("active_text")) or summary,
                reason=(
                    "已落在 jingxuan，左侧推荐入口可见，但尚未进入真正可滚动推荐流。"
                    + (
                        f" 页面存在常见下载/安装文案 {download_phrase}，仅视作普通 jingxuan 文案，不单独判定为 open-app 阻断。"
                        if download_phrase
                        else ""
                    )
                    + f" {readiness_reason}"
                ),
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if on_jingxuan:
            screenshot = self._capture(
                f"douyin_public_jingxuan_{debug_label}" if capture and debug_label else "douyin_public_jingxuan"
            ) if capture else None
            return PageStateSnapshot(
                state="public_jingxuan_landing",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text((active_feed or {}).get("active_text")) or summary,
                reason=(
                    "当前落在 jingxuan 过渡页，尚未进入左侧推荐后的真实推荐流。"
                    + (
                        f" 页面存在常见下载/安装文案 {download_phrase}，仅视作普通 jingxuan 文案，不单独判定为 open-app 阻断。"
                        if download_phrase
                        else ""
                    )
                    + f" {readiness_reason}"
                ),
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if active_feed is not None:
            screenshot = self._capture(
                f"douyin_visual_feed_unstable_{debug_label}" if capture and debug_label else "douyin_visual_feed_unstable"
            ) if capture else None
            return PageStateSnapshot(
                state="visual_feed_unstable",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=_summarize_text(active_feed.get("active_text")) or summary,
                reason=f"页面看起来像推荐流，但当前激活项未达到可提取稳定度。{readiness_reason}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if recommend_route:
            screenshot = self._capture(
                f"douyin_recommend_feed_shell_{debug_label}" if capture and debug_label else "douyin_recommend_feed_shell"
            ) if capture else None
            return PageStateSnapshot(
                state="recommend_feed_shell",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                reason=(
                    "推荐页已打开，但当前仍在等待中心视频区域或交互焦点完全稳定。"
                    + (
                        f" 页面存在常见下载/安装文案 {download_phrase}，在 recommend 路由中仅视作普通页面文案，不单独判定为下载/异常页。"
                        if download_phrase
                        else ""
                    )
                    + f" {readiness_reason}"
                ),
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if looks_like_feed:
            screenshot = self._capture(
                f"douyin_public_feed_{debug_label}" if capture and debug_label else "douyin_public_feed"
            ) if capture else None
            return PageStateSnapshot(
                state="public_feed",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                reason=f"页面具备推荐流外观，但未识别到稳定激活项。{readiness_reason}",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        if page_contains_any_text(self.page, selectors.FOOTER_ABNORMAL_HINTS):
            screenshot = self._capture(
                f"douyin_footer_state_{debug_label}" if capture and debug_label else "douyin_footer_state"
            ) if capture else None
            return PageStateSnapshot(
                state="abnormal/footer/download_page",
                page_url=current_url,
                page_title=current_title,
                visible_text_summary=summary,
                reason="当前页面停留在异常/页脚态，未进入推荐流",
                screenshot_path=screenshot,
                blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                missing_readiness_anchors=missing_anchors,
            )

        return PageStateSnapshot(
            state="abnormal/footer/download_page",
            page_url=current_url,
            page_title=current_title,
            visible_text_summary=summary,
            reason=f"当前页面未识别到稳定可提取推荐流。{readiness_reason}",
            blocking_reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            missing_readiness_anchors=missing_anchors,
        )

    def read_current_candidate(self, debug_label: str | None = None) -> FeedCandidateSnapshot:
        page_state = self.classify_page_state(debug_label=debug_label, capture=True)
        self.logger.info(
            "douyin page-state before extraction",
            extra={
                "page_state": page_state.state,
                "page_url": page_state.page_url,
                "page_title": page_state.page_title,
                "reason": page_state.reason,
                "detected_phrase": page_state.detected_phrase,
                "missing_readiness_anchors": page_state.missing_readiness_anchors,
                "state_screenshot_path": page_state.screenshot_path,
            },
        )
        if page_state.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            raise self._snapshot_to_blocking_error(page_state, page_name="douyin_feed")
        pre_extract_screenshot_path = self._capture(
            f"douyin_feed_before_extract_{debug_label}" if debug_label else "douyin_feed_before_extract"
        )
        candidate = self._collect_feed_snapshot(
            pre_extract_screenshot_path=pre_extract_screenshot_path,
            active_state=self._extract_active_feed_state(),
        )
        if not candidate.creator_profile_url or not any(
            (candidate.like_count_raw, candidate.comment_count_raw, candidate.favorite_count_raw, candidate.share_count_raw)
        ):
            screenshot = self._capture(
                f"douyin_feed_unstable_extract_{debug_label}" if debug_label else "douyin_feed_unstable_extract"
            )
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="当前页面虽处于推荐流，但作者链接或互动指标提取不稳定",
                page_name="douyin_feed",
                page_state="visual_feed_unstable",
                screenshot_path=screenshot,
                required_user_action="Please scroll to a stable active card, dismiss overlays, wait for feed hydration, and then retry extraction on the current page.",
                resumable=True,
            )
        return candidate

    def observe_interactable_feed(self, debug_label: str | None = None) -> FeedCandidateSnapshot:
        page_state = self.classify_page_state(debug_label=debug_label, capture=True)
        self.logger.info(
            "douyin page-state before browse loop",
            extra={
                "page_state": page_state.state,
                "page_url": page_state.page_url,
                "page_title": page_state.page_title,
                "reason": page_state.reason,
                "missing_readiness_anchors": page_state.missing_readiness_anchors,
                "state_screenshot_path": page_state.screenshot_path,
            },
        )
        if page_state.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            raise self._snapshot_to_blocking_error(page_state, page_name="douyin_feed_interactable")
        return self._collect_feed_snapshot(active_state=self._extract_active_feed_state())

    def _collect_feed_snapshot(
        self,
        active_state: dict | None = None,
        pre_extract_screenshot_path: str | None = None,
    ) -> FeedCandidateSnapshot:
        card = first_visible_locator(self.page, selectors.ACTIVE_CARD_SELECTORS)
        raw_text = (active_state or {}).get("active_text") or (locator_text(card) if card is not None else None) or body_text(self.page)
        packed_like, packed_comment, packed_favorite, packed_share = _extract_metric_pack(raw_text)
        like_count_raw = (
            (first_text(card, selectors.LIKE_COUNT_SELECTORS) if card is not None else None)
            or first_text(self.page, selectors.LIKE_COUNT_SELECTORS)
            or packed_like
            or _extract_metric(raw_text, "点赞")
        )
        comment_count_raw = (
            (first_text(card, selectors.COMMENT_COUNT_SELECTORS) if card is not None else None)
            or first_text(self.page, selectors.COMMENT_COUNT_SELECTORS)
            or packed_comment
            or _extract_metric(raw_text, "评论")
        )
        favorite_count_raw = (
            (first_text(card, selectors.FAVORITE_COUNT_SELECTORS) if card is not None else None)
            or first_text(self.page, selectors.FAVORITE_COUNT_SELECTORS)
            or packed_favorite
            or _extract_metric(raw_text, "收藏")
        )
        share_count_raw = (
            (first_text(card, selectors.SHARE_COUNT_SELECTORS) if card is not None else None)
            or first_text(self.page, selectors.SHARE_COUNT_SELECTORS)
            or packed_share
            or _extract_metric(raw_text, "分享")
        )
        creator_name = (
            _sanitize_creator_name((active_state or {}).get("creator_name"))
            or _sanitize_creator_name(first_text(card, selectors.CREATOR_NAME_SELECTORS) if card is not None else None)
            or _extract_creator_name(raw_text)
            or _sanitize_creator_name(first_text(self.page, selectors.CREATOR_NAME_SELECTORS))
        )
        creator_profile_url = (
            (active_state or {}).get("creator_profile_url")
            or (first_attribute(card, selectors.CREATOR_LINK_SELECTORS, "href") if card is not None else None)
            or first_attribute(self.page, selectors.CREATOR_LINK_SELECTORS, "href")
        )
        video_url = (
            (active_state or {}).get("video_url")
            or (first_attribute(card, selectors.VIDEO_LINK_SELECTORS, "href") if card is not None else None)
            or first_attribute(self.page, selectors.VIDEO_LINK_SELECTORS, "href")
        )
        video_url = _normalize_url(video_url)
        creator_profile_url = _normalize_url(creator_profile_url)
        if self._looks_like_self_profile(creator_profile_url):
            creator_profile_url = None
        active_text_summary = _summarize_text(raw_text, limit=220)
        total_interaction = " ".join(
            filter(
                None,
                [
                    f"👍{like_count_raw}" if like_count_raw else None,
                    f"💬{comment_count_raw}" if comment_count_raw else None,
                    f"↗️{share_count_raw}" if share_count_raw else None,
                    f"⭐{favorite_count_raw}" if favorite_count_raw else None,
                ],
            )
        ) or None

        return FeedCandidateSnapshot(
            creator_name=creator_name,
            creator_profile_url=creator_profile_url,
            video_url=video_url,
            video_url_capture_source="dom" if video_url else "none",
            publish_time_raw=(first_text(card, selectors.PUBLISH_TIME_SELECTORS) if card is not None else None)
            or first_text(self.page, selectors.PUBLISH_TIME_SELECTORS)
            or _extract_publish_time(raw_text),
            total_interaction_text=total_interaction,
            like_count_raw=like_count_raw,
            comment_count_raw=comment_count_raw,
            favorite_count_raw=favorite_count_raw,
            share_count_raw=share_count_raw,
            ai_generated_flag=_contains_any(raw_text, selectors.AI_HINTS),
            is_live=_looks_like_live_feed_item(raw_text, creator_profile_url=creator_profile_url, video_url=video_url),
            is_ad=_contains_any(raw_text, selectors.AD_HINTS),
            caption_text=raw_text.splitlines()[0].strip() if raw_text else None,
            raw_text=raw_text,
            video_title_text=_extract_video_title_text(raw_text),
            video_description_raw=_clean_video_description_text(raw_text),
            feed_selector_hint=(active_state or {}).get("container_hint"),
            feed_identity=_build_feed_identity(
                video_url=video_url,
                creator_profile_url=creator_profile_url,
                creator_name=creator_name,
                like_count_raw=like_count_raw,
                comment_count_raw=comment_count_raw,
                favorite_count_raw=favorite_count_raw,
                share_count_raw=share_count_raw,
                text_summary=active_text_summary,
            ),
            active_text_summary=active_text_summary,
            page_url=self.page.url,
            page_title=self._safe_title(),
            pre_extract_screenshot_path=pre_extract_screenshot_path,
        )

    def collect_content_snapshot(
        self,
        candidate: FeedCandidateSnapshot,
        debug_label: str | None = None,
        keyframe_count: int = 4,
    ) -> FeedCandidateSnapshot:
        snapshot = replace(candidate)
        network_match = self._match_recent_aweme_item(candidate)

        # 直播和商品卡不点分享按钮，也不提取视频链接
        if snapshot.is_live:
            snapshot.video_url = None
            snapshot.video_url_capture_source = "live_skipped"

        elif _looks_like_commerce_feed_item(snapshot.raw_text):
            snapshot.is_commerce = True
            snapshot.video_url = None
            snapshot.video_url_capture_source = "commerce_skipped"

        else:
            # 普通视频只接受右下角「分享 -> 复制链接」拿到的永久链接
            share_video_url = self._copy_current_video_share_link(debug_label=debug_label)

            if share_video_url:
                snapshot.video_url = share_video_url
                snapshot.video_url_capture_source = "share_copy"
            else:
                snapshot.video_url = None
                snapshot.video_url_capture_source = "none"
            # 这里处理 video_url，只信复制链接
            description_raw = _clean_video_description_text(snapshot.raw_text)
            network_description = _clean_video_description_text(network_match.get("description")) if network_match else None
            network_expanded_description = _clean_video_description_text(
                network_match.get("description"),
                limit=960,
            ) if network_match else None
            snapshot.video_title_text = _merge_description_text(
                _extract_video_title_text(snapshot.raw_text),
                _extract_video_title_text(network_match.get("description")) if network_match else None,
            )
            snapshot.video_description_raw = _merge_description_text(description_raw, network_description)
            snapshot.expanded_description_text = _merge_description_text(
                _clean_video_description_text(snapshot.raw_text, limit=960),
                network_expanded_description,
            )
            if not _is_meaningfully_distinct(snapshot.expanded_description_text, snapshot.video_description_raw):
                snapshot.expanded_description_text = None
            raw_metadata_source = " ".join(
                part
                for part in (
                    snapshot.raw_text,
                    network_match.get("description") if network_match else None,
                )
                if part
            )
            snapshot.chapter_texts = _extract_chapter_texts(raw_metadata_source)
            snapshot.related_search_terms = _extract_related_search_terms(raw_metadata_source)
            snapshot.author_statement_texts = _extract_author_statement_texts(raw_metadata_source)
            snapshot.visible_subtitle_segments = self._collect_visible_subtitle_segments()
            comment_result = self._collect_top_comments(snapshot, debug_label=debug_label)
            snapshot.top_comments = comment_result.comments
            snapshot.top_comments_source = comment_result.source
            snapshot.comment_collection_status = comment_result.status
            snapshot.comment_collection_debug = comment_result.debug
            snapshot.keyframe_paths = self._capture_keyframes(debug_label=debug_label, count=keyframe_count)
            snapshot.video_text_bundle = _build_video_text_bundle(
                title_text=snapshot.video_title_text,
                description_text=snapshot.video_description_raw,
                expanded_description_text=snapshot.expanded_description_text,
                chapter_texts=snapshot.chapter_texts,
                related_search_terms=snapshot.related_search_terms,
                author_statement_texts=snapshot.author_statement_texts,
                visible_subtitle_segments=snapshot.visible_subtitle_segments,
                top_comments=snapshot.top_comments,
            )
            self.logger.info(
                "content snapshot collected",
                extra={
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "feed_identity": snapshot.feed_identity,
                    "creator_name": snapshot.creator_name,
                    "video_url": snapshot.video_url,
                    "video_url_capture_source": snapshot.video_url_capture_source,
                    "chapter_count": len(snapshot.chapter_texts),
                    "related_search_count": len(snapshot.related_search_terms),
                    "author_statement_count": len(snapshot.author_statement_texts),
                    "subtitle_count": len(snapshot.visible_subtitle_segments),
                    "comment_count": len(snapshot.top_comments),
                    "comment_source": snapshot.top_comments_source,
                    "comment_collection_status": snapshot.comment_collection_status,
                    "comment_collection_debug": snapshot.comment_collection_debug,
                    "keyframe_count": len(snapshot.keyframe_paths),
                    "debug_label": debug_label,
                },
            )
            return snapshot

    def _collect_visible_subtitle_segments(self, sample_count: int = 3) -> list[str]:
        merged: list[str] = []
        for index in range(max(1, sample_count)):
            state = self._extract_active_feed_state()
            sample = _extract_visible_subtitle_sample((state or {}).get("active_text"))
            merged = _merge_subtitle_segments(merged, sample)
            if index < sample_count - 1:
                self._wait_for_timeout_safe(850, reason=f"subtitle_sample_{index + 1}")
        return merged

    def _collect_top_comments(
        self,
        candidate: FeedCandidateSnapshot,
        debug_label: str | None = None,
    ) -> CommentCollectionResult:
        video_id = _extract_video_id_from_url(candidate.video_url)
        if video_id:
            self._clear_recent_comment_payload(video_id)
        self.logger.info(
            "comment collection started",
            extra={
                "page_url": candidate.page_url,
                "page_title": candidate.page_title,
                "creator_name": candidate.creator_name,
                "video_url": candidate.video_url,
                "video_id": video_id,
                "debug_label": debug_label,
            },
        )

        triggered = self._open_comments_panel(candidate=candidate, debug_label=debug_label)
        if triggered:
            self._wait_for_timeout_safe(1_200, reason="comment_panel_network_wait")
        panel_visible = self._is_comment_panel_open()
        network_comments, network_url = self._get_recent_network_comments(video_id)
        self.logger.info(
            "comment collection network snapshot",
            extra={
                "debug_label": debug_label,
                "video_id": video_id,
                "triggered": triggered,
                "panel_visible": panel_visible,
                "network_count": len(network_comments),
                "comment_api_url": network_url,
            },
        )

        ui_comments: list[CommentSnippet] = []
        parse_failed = False
        if len(network_comments) < 3 and panel_visible:
            ui_comments, parse_failed = self._extract_ui_comment_items()
            self.logger.info(
                "comment collection ui snapshot",
                extra={
                    "debug_label": debug_label,
                    "video_id": video_id,
                    "ui_count": len(ui_comments),
                    "parse_failed": parse_failed,
                },
            )

        result = _build_comment_collection_result(
            network_comments=network_comments,
            ui_comments=ui_comments,
            triggered=triggered,
            panel_visible=panel_visible,
            parse_failed=parse_failed,
            network_url=network_url,
        )

        self.logger.info(
            "comment collection completed",
            extra={
                "debug_label": debug_label,
                "video_id": video_id,
                "comment_source": result.source,
                "comment_collection_status": result.status,
                "comment_collection_debug": result.debug,
                "network_count": result.network_count,
                "ui_count": result.ui_count,
                "final_comment_count": len(result.comments),
            },
        )
        panel_closed = True
        if triggered or panel_visible:
            panel_closed = self._close_comments_panel(debug_label=debug_label)
        self._dismiss_login_modal(reason="comment_collection_finalize", debug_label=debug_label)
        if not panel_closed:
            self.logger.warning(
                "comment panel remained open after close attempts",
                extra={
                    "debug_label": debug_label,
                    "video_id": video_id,
                    "comment_collection_status": result.status,
                },
            )
        return result

    def _open_comments_panel(
        self,
        candidate: FeedCandidateSnapshot | None = None,
        debug_label: str | None = None,
    ) -> bool:
        self._dismiss_login_modal(reason="comment_preflight", debug_label=debug_label)
        self._dismiss_feed_side_panel(reason="comment_preflight", debug_label=debug_label)
        if self._is_comment_panel_open():
            return True
        strategies: list[tuple[str, object]] = []
        button_candidates: list[tuple[str, object]] = []
        seen_selectors: set[str] = set()
        expected_count = (candidate.comment_count_raw or "").strip() if candidate is not None else ""
        exact_count_locator = self._comment_count_locator(expected_count)
        if exact_count_locator is not None:
            for selector, locator in [
                ("comment_count_exact", exact_count_locator),
                ("comment_count_exact_button", exact_count_locator.locator("xpath=ancestor-or-self::button[1]").first),
                (
                    "comment_count_exact_role_button",
                    exact_count_locator.locator("xpath=ancestor-or-self::*[@role='button'][1]").first,
                ),
            ]:
                if selector in seen_selectors or not self._is_likely_comment_target(locator):
                    continue
                button_candidates.append((selector, locator))
                seen_selectors.add(selector)
        for selector in selectors.COMMENT_BUTTON_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=600)
            if locator is None or selector in seen_selectors or not self._is_likely_comment_target(locator):
                continue
            button_candidates.append((selector, locator))
            seen_selectors.add(selector)
        count_locator = first_visible_locator(self.page, selectors.COMMENT_COUNT_SELECTORS, timeout_ms=600)
        if count_locator is not None:
            for selector, locator in [
                ("comment_count", count_locator),
                ("comment_count_button", count_locator.locator("xpath=ancestor-or-self::button[1]").first),
                ("comment_count_role_button", count_locator.locator("xpath=ancestor-or-self::*[@role='button'][1]").first),
            ]:
                if selector in seen_selectors or not self._is_likely_comment_target(locator):
                    continue
                button_candidates.append((selector, locator))
                seen_selectors.add(selector)
        strategies.extend(button_candidates)
        strategies.extend((f"{selector}_force", locator) for selector, locator in button_candidates)

        clicked = False
        for method, target in strategies:
            try:
                if method == "keyboard":
                    self.page.keyboard.press(str(target))
                elif method.endswith("_force"):
                    target.click(timeout=1_500, force=True)
                else:
                    target.click(timeout=1_500)
                clicked = True
            except Exception:
                continue
            self._wait_for_timeout_safe(700, reason=f"comment_panel_open_{method}")
            if self._is_comment_panel_open():
                return True
            if self._is_login_modal_open():
                self.logger.info(
                    "comment panel open triggered login modal",
                    extra={"debug_label": debug_label, "method": method},
                )
                self._dismiss_login_modal(reason=f"comment_open:{method}", debug_label=debug_label)
                clicked = False
                continue
        return clicked and self._is_comment_panel_open()

    def _is_comment_panel_open(self) -> bool:
        panel = first_visible_locator(self.page, selectors.COMMENT_PANEL_SELECTORS, timeout_ms=600)
        return panel is not None

    def _has_feed_side_panel(self) -> bool:
        body = body_text(self.page, timeout_ms=900)
        return any(hint in body for hint in selectors.FEED_SIDE_PANEL_HINTS)

    def _dismiss_feed_side_panel(self, reason: str, debug_label: str | None = None) -> bool:
        if not self._has_feed_side_panel():
            return True
        close_button = first_visible_locator(self.page, selectors.FEED_SIDE_PANEL_CLOSE_SELECTORS, timeout_ms=500)
        if close_button is not None and self._is_likely_panel_close_target(close_button, min_y=48):
            try:
                close_button.click(timeout=800)
                self._wait_for_timeout_safe(450, reason=f"feed_side_panel_close:{reason}")
                if self._looks_like_self_profile(self.page.url):
                    return self._recover_from_self_profile(debug_label=debug_label)
                if not self._has_feed_side_panel():
                    self.logger.info(
                        "feed side panel dismissed",
                        extra={"debug_label": debug_label, "method": "selector", "reason": reason},
                    )
                    return True
            except Exception:
                pass
        for key in ("Escape", "Escape"):
            try:
                self.page.keyboard.press(key)
                self._wait_for_timeout_safe(350, reason=f"feed_side_panel_key:{reason}")
                if self._looks_like_self_profile(self.page.url):
                    return self._recover_from_self_profile(debug_label=debug_label)
                if not self._has_feed_side_panel():
                    self.logger.info(
                        "feed side panel dismissed",
                        extra={"debug_label": debug_label, "method": f"keyboard:{key}", "reason": reason},
                    )
                    return True
            except Exception:
                continue
        return not self._has_feed_side_panel()

    def _comment_count_locator(self, expected_count: str | None) -> object | None:
        if not expected_count:
            return None
        card = first_visible_locator(self.page, selectors.ACTIVE_CARD_SELECTORS, timeout_ms=450)
        if card is None:
            return None
        candidates = [
            card.locator(f'text="{expected_count}"').first,
            card.locator(f"xpath=.//*[normalize-space(text())='{expected_count}']").first,
        ]
        for locator in candidates:
            try:
                if locator is not None and locator.is_visible(timeout=400):
                    return locator
            except Exception:
                continue
        return None

    def _is_likely_comment_target(self, locator) -> bool:
        if locator is None:
            return False
        try:
            if not locator.is_visible(timeout=350):
                return False
        except Exception:
            return False
        try:
            box = locator.bounding_box()
        except Exception:
            box = None
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        if box is None:
            return True
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2
        if center_x < viewport["width"] * 0.68:
            return False
        if center_y < 120 or center_y > viewport["height"] - 70:
            return False
        return True

    def _is_likely_panel_close_target(self, locator, min_y: int = 0) -> bool:
        if locator is None:
            return False
        try:
            if not locator.is_visible(timeout=350):
                return False
        except Exception:
            return False
        try:
            box = locator.bounding_box()
        except Exception:
            box = None
        if box is None:
            return False
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2
        if center_x < viewport["width"] * 0.55:
            return False
        if center_y < min_y or center_y > viewport["height"] - 40:
            return False
        if box["width"] > 160 or box["height"] > 120:
            return False
        return True

    def _is_login_modal_open(self) -> bool:
        if not any(
            first_visible_locator(self.page, [f"text={hint}"], timeout_ms=200) is not None
            for hint in selectors.LOGIN_MODAL_TEXT_HINTS
        ):
            return False
        return True

    def _dismiss_login_modal(self, reason: str, debug_label: str | None = None) -> bool:
        if not self._is_login_modal_open():
            return True
        for selector in selectors.LOGIN_MODAL_CLOSE_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=250)
            if locator is None:
                continue
            try:
                locator.click(timeout=700)
                self._wait_for_timeout_safe(300, reason=f"login_modal_close:{reason}")
                if not self._is_login_modal_open():
                    self.logger.info(
                        "login modal dismissed",
                        extra={"debug_label": debug_label, "method": f"selector:{selector}", "reason": reason},
                    )
                    return True
            except Exception:
                continue
        for key in ("Escape", "Escape"):
            try:
                self.page.keyboard.press(key)
                self._wait_for_timeout_safe(250, reason=f"login_modal_key:{reason}")
                if not self._is_login_modal_open():
                    self.logger.info(
                        "login modal dismissed",
                        extra={"debug_label": debug_label, "method": f"keyboard:{key}", "reason": reason},
                    )
                    return True
            except Exception:
                continue
        for hint in selectors.LOGIN_MODAL_TEXT_HINTS:
            anchor = first_visible_locator(self.page, [f"text={hint}"], timeout_ms=200)
            if anchor is None:
                continue
            try:
                box = anchor.evaluate(
                    """(el) => {
                        let node = el;
                        while (node && node !== document.body) {
                            const rect = node.getBoundingClientRect();
                            if (rect.width >= 320 && rect.height >= 220) {
                                return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                            }
                            node = node.parentElement;
                        }
                        const rect = el.getBoundingClientRect();
                        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                    }"""
                )
            except Exception:
                box = None
            if not box:
                continue
            try:
                for method, x, y in [
                    ("back_hotspot", box["x"] + 24, box["y"] + 24),
                    ("close_hotspot", box["x"] + box["width"] - 24, box["y"] + 24),
                ]:
                    self.page.mouse.click(x, y)
                    self._wait_for_timeout_safe(300, reason=f"login_modal_hotspot:{reason}")
                    if not self._is_login_modal_open():
                        self.logger.info(
                            "login modal dismissed",
                            extra={"debug_label": debug_label, "method": method, "reason": reason},
                        )
                        return True
            except Exception:
                continue
        return not self._is_login_modal_open()
    #关闭评论面板
    def _close_comments_panel(
        self,
        debug_label: str | None = None,
    ) -> bool:
        """Close Douyin comment panel reliably.

        Returns True if the page no longer looks like the comment panel is open.
        """
        def _get_body_text(limit: int = 1200) -> str:
            try:
                text = self.page.locator("body").inner_text(timeout=1200)
            except Exception:
                return ""
            return text[:limit]

        def _panel_is_open() -> bool:
            body_text = _get_body_text()

            comment_hints = [
                "全部评论",
                "留下你的精彩评论吧",
                "暂无评论",
                "抢首评",
                "加载中",
            ]

            footer_pollution_hints = [
                "开启读屏标签",
                "读屏标签已关闭",
                "下载抖音精选",
                "京ICP备",
                "网络文化经营许可证",
            ]

            # 评论面板明确打开
            if any(hint in body_text for hint in comment_hints):
                return True

            # 页面已经被面板/滚动污染成页脚，也当作未恢复干净
            if any(hint in body_text for hint in footer_pollution_hints):
                return True

            return False

        def _log_state(method: str) -> bool:
            panel_open = _panel_is_open()
            self.logger.info(
                "comment panel close final state",
                extra={
                    "debug_label": debug_label,
                    "method": method,
                    "panel_open": panel_open,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "body_preview": _get_body_text(limit=300),
                },
            )
            return not panel_open

        try:
            # 1. 先按 Escape，多按几次。第一下经常只是取消输入框焦点。
            for _ in range(5):
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(300)
                    if not _panel_is_open():
                        return _log_state("escape")
                except Exception:
                    pass

            # 2. 尝试点击常见关闭 selector。
            close_selectors = [
                '[aria-label*="关闭"]',
                '[title*="关闭"]',
                'button:has-text("关闭")',
                'div[role="button"]:has-text("关闭")',
                'text=关闭',
            ]

            for selector in close_selectors:
                try:
                    locator = self.page.locator(selector).first
                    if locator.count() > 0 and locator.is_visible(timeout=500):
                        locator.click(timeout=1000)
                        self.page.wait_for_timeout(600)
                        if not _panel_is_open():
                            return _log_state(f"selector:{selector}")
                except Exception:
                    continue

            # 3. 用 DOM 几何定位评论面板，并点击面板顶部可能的关闭按钮。
            # 这个比找文字更可靠。
            try:
                result = self.page.evaluate(
                    """
                    () => {
                        const vw = window.innerWidth || document.documentElement.clientWidth;
                        const vh = window.innerHeight || document.documentElement.clientHeight;

                        function visible(el) {
                            const style = window.getComputedStyle(el);
                            if (!style) return false;
                            if (style.display === "none" || style.visibility === "hidden") return false;
                            if (Number(style.opacity || "1") === 0) return false;

                            const r = el.getBoundingClientRect();
                            if (!r || r.width <= 0 || r.height <= 0) return false;

                            return r.right > 0 && r.left < vw && r.bottom > 0 && r.top < vh;
                        }

                        function textOf(el) {
                            return [
                                el.innerText || "",
                                el.textContent || "",
                                el.getAttribute("aria-label") || "",
                                el.getAttribute("title") || "",
                                el.getAttribute("class") || "",
                                el.getAttribute("data-e2e") || "",
                            ].join(" ");
                        }

                        function rectObj(el) {
                            const r = el.getBoundingClientRect();
                            return {
                                left: Math.round(r.left),
                                top: Math.round(r.top),
                                right: Math.round(r.right),
                                bottom: Math.round(r.bottom),
                                width: Math.round(r.width),
                                height: Math.round(r.height),
                                cx: Math.round(r.left + r.width / 2),
                                cy: Math.round(r.top + r.height / 2),
                            };
                        }

                        // A. 找评论面板容器：包含“全部评论/留下你的精彩评论吧/暂无评论”的大块区域
                        const all = Array.from(document.querySelectorAll("div, section, aside"));
                        const panels = [];

                        for (const el of all) {
                            if (!visible(el)) continue;

                            const text = textOf(el);
                            if (
                                !text.includes("全部评论") &&
                                !text.includes("留下你的精彩评论吧") &&
                                !text.includes("暂无评论") &&
                                !text.includes("抢首评")
                            ) {
                                continue;
                            }

                            const r = el.getBoundingClientRect();

                            // 评论面板通常较大，并且在页面右侧或中右侧
                            if (r.width < 250 || r.height < 250) continue;
                            if (r.left < vw * 0.35) continue;

                            panels.push({
                                el,
                                score: r.width * r.height + r.left,
                                rect: rectObj(el),
                                text: text.slice(0, 120),
                            });
                        }

                        panels.sort((a, b) => b.score - a.score);

                        if (panels.length === 0) {
                            return {
                                clicked: false,
                                reason: "no_comment_panel_found",
                                panels: [],
                            };
                        }

                        const panel = panels[0];
                        const pr = panel.el.getBoundingClientRect();

                        // B. 在评论面板顶部区域找小按钮，优先 close/X/关闭
                        const clickableNodes = Array.from(
                            document.querySelectorAll("button, [role='button'], [aria-label], [title], svg, path, div")
                        );

                        const candidatesMap = new Map();

                        function clickableAncestor(node) {
                            let cur = node;
                            for (let i = 0; i < 7 && cur; i++) {
                                const r = cur.getBoundingClientRect();
                                const tag = (cur.tagName || "").toLowerCase();
                                const role = cur.getAttribute("role") || "";
                                const cls = cur.getAttribute("class") || "";
                                const aria = cur.getAttribute("aria-label") || "";
                                const title = cur.getAttribute("title") || "";

                                const goodSize =
                                    r.width >= 14 &&
                                    r.width <= 90 &&
                                    r.height >= 14 &&
                                    r.height <= 90;

                                const maybeClickable =
                                    tag === "button" ||
                                    role === "button" ||
                                    aria ||
                                    title ||
                                    cls;

                                if (goodSize && maybeClickable) {
                                    return cur;
                                }

                                cur = cur.parentElement;
                            }
                            return node;
                        }

                        for (const node of clickableNodes) {
                            const el = clickableAncestor(node);
                            if (!el || !visible(el)) continue;

                            const r = el.getBoundingClientRect();
                            const cx = r.left + r.width / 2;
                            const cy = r.top + r.height / 2;

                            // 必须在评论面板内部/附近
                            if (cx < pr.left || cx > pr.right) continue;

                            // 只看评论面板顶部 25% 区域，关闭按钮通常在顶部
                            if (cy < pr.top || cy > pr.top + pr.height * 0.28) continue;

                            if (r.width > 90 || r.height > 90) continue;

                            const text = textOf(el);
                            const lower = text.toLowerCase();

                            let score = 0;

                            if (text.includes("关闭")) score += 100;
                            if (lower.includes("close")) score += 100;
                            if (lower.includes("x")) score += 15;

                            // 越靠右上越像关闭按钮
                            score += (cx - pr.left) / Math.max(1, pr.width) * 40;
                            score += (1 - (cy - pr.top) / Math.max(1, pr.height)) * 40;

                            const key = [
                                Math.round(r.left),
                                Math.round(r.top),
                                Math.round(r.width),
                                Math.round(r.height),
                            ].join(":");

                            if (!candidatesMap.has(key)) {
                                candidatesMap.set(key, {
                                    el,
                                    score,
                                    rect: rectObj(el),
                                    text: text.trim().slice(0, 100),
                                });
                            }
                        }

                        const candidates = Array.from(candidatesMap.values())
                            .sort((a, b) => b.score - a.score);

                        const debugCandidates = candidates.slice(0, 8).map(c => ({
                            score: Math.round(c.score),
                            rect: c.rect,
                            text: c.text,
                        }));

                        if (candidates.length > 0) {
                            const best = candidates[0];
                            best.el.click();

                            return {
                                clicked: true,
                                reason: "clicked_panel_top_close_candidate",
                                panel: {
                                    rect: panel.rect,
                                    text: panel.text,
                                },
                                target: {
                                    score: Math.round(best.score),
                                    rect: best.rect,
                                    text: best.text,
                                },
                                candidates: debugCandidates,
                            };
                        }

                        // C. 如果没有找到按钮，点击评论面板外的左侧视频区域，让面板失焦
                        const clickX = Math.round(vw * 0.28);
                        const clickY = Math.round(vh * 0.50);
                        const target = document.elementFromPoint(clickX, clickY);

                        if (target) {
                            target.click();
                            return {
                                clicked: true,
                                reason: "clicked_outside_panel",
                                panel: {
                                    rect: panel.rect,
                                    text: panel.text,
                                },
                                targetPoint: { x: clickX, y: clickY },
                                candidates: debugCandidates,
                            };
                        }

                        return {
                            clicked: false,
                            reason: "no_close_candidate_and_no_outside_target",
                            panel: {
                                rect: panel.rect,
                                text: panel.text,
                            },
                            candidates: debugCandidates,
                        };
                    }
                    """
                )

                self.logger.info(
                    "comment panel close candidate clicked",
                    extra={
                        "debug_label": debug_label,
                        "result": result,
                    },
                )

                self.page.wait_for_timeout(700)

                # 如果刚才只是点了外部区域，再补 Escape
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(400)
                except Exception:
                    pass

                if not _panel_is_open():
                    return _log_state("geometry_or_outside_click")

            except Exception as exc:
                self.logger.info(
                    "failed to click comment panel close candidate",
                    extra={
                        "debug_label": debug_label,
                        "error": str(exc),
                    },
                )

            # 4. 最后兜底：点击左上角视频安全区域，不点右侧按钮栏，避免误入直播/分享。
            try:
                viewport = self.page.viewport_size or {"width": 1440, "height": 900}

                safe_points = [
                    (0.25, 0.30),
                    (0.30, 0.50),
                    (0.22, 0.70),
                ]

                for x_ratio, y_ratio in safe_points:
                    self.page.mouse.click(
                        int(viewport["width"] * x_ratio),
                        int(viewport["height"] * y_ratio),
                    )
                    self.page.wait_for_timeout(300)
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(400)

                    if not _panel_is_open():
                        return _log_state("safe_area_click_escape")

            except Exception:
                pass

            panel_open = _panel_is_open()

            self.logger.info(
                "comment panel close final state",
                extra={
                    "debug_label": debug_label,
                    "method": "failed_all_attempts",
                    "panel_open": panel_open,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "body_preview": _get_body_text(limit=500),
                },
            )

            if panel_open:
                self.logger.warning(
                    "comment panel remained open after close attempts",
                    extra={
                        "debug_label": debug_label,
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                    },
                )

                self._recover_recommend_feed_if_polluted(
                    debug_label=f"{debug_label}_after_comment_close_failed"
                )

            return not panel_open

        except Exception as exc:
            self.logger.warning(
                "failed to close comment panel",
                extra={
                    "debug_label": debug_label,
                    "error": str(exc),
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )
            return False
        
    def _page_text_looks_polluted(self) -> bool:
        try:
            body_text = self.page.locator("body").inner_text(timeout=1200)
        except Exception:
            return False

        footer_hints = [
            "开启读屏标签",
            "读屏标签已关闭",
            "京ICP备",
            "京公网安备",
            "用户服务协议",
            "隐私政策",
            "站点地图",
        ]

        video_hints = [
            "听抖音",
            "发送",
            "倍速",
            "清屏",
            "连播",
            "@",
            "评论",
        ]

        has_footer = any(hint in body_text for hint in footer_hints)
        has_video = any(hint in body_text for hint in video_hints)

        # 只有页脚明显存在，而且没有视频信息，才算污染
        return has_footer and not has_video
    
    def _recover_recommend_feed_if_polluted(
        self,
        debug_label: str | None = None,
    ) -> bool:
        """Recover from footer/polluted page state back to Douyin recommend feed.

        This is used when comment panel closing leaves the page reading footer/global text
        instead of a real active video card.
        """
        try:
            is_live_url = "/root/live/" in (self.page.url or "")
            is_polluted = self._page_text_looks_polluted()

            if not is_live_url and not is_polluted:
                return True

            self.logger.warning(
                "recovering recommend feed from polluted/live state",
                extra={
                    "debug_label": debug_label,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "is_live_url": is_live_url,
                    "is_polluted": is_polluted,
                },
            )

            # 1. 先按 Escape，关闭残留弹层
            for _ in range(3):
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(250)
                except Exception:
                    pass

            # 2. 强制回推荐流，避免继续停留在页脚/直播间/错误状态
            try:
                self.page.goto(
                    "https://www.douyin.com/?recommend=1&from_nav=1",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
            except Exception:
                pass

            self.page.wait_for_timeout(3500)

            # 3. 再按 Escape 清浮层
            for _ in range(2):
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(250)
                except Exception:
                    pass

            # 4. 尝试往下一条稳定视频推进
            try:
                self.scroll_to_next_video(
                    debug_label=f"{debug_label}_recover_next" if debug_label else "recover_next",
                )
            except Exception:
                pass

            self.page.wait_for_timeout(1200)

            recovered = not self._page_text_looks_polluted() and "/root/live/" not in (
                self.page.url or ""
            )

            self.logger.info(
                "recommend feed recovery completed",
                extra={
                    "debug_label": debug_label,
                    "recovered": recovered,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )

            return recovered

        except Exception as exc:
            self.logger.warning(
                "failed to recover recommend feed from polluted state",
                extra={
                    "debug_label": debug_label,
                    "error": str(exc),
                    "page_url": self.page.url if self.page else None,
                },
            )
            return False
        
    def _extract_ui_comment_items(self) -> tuple[list[CommentSnippet], bool]:
        try:
            items = self.page.evaluate(
                """({ panelSelectors, itemSelectors }) => {
                    const cleanText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                    const isMetaLine = (line) => {
                        if (!line) return true;
                        if (/^\\d+(?:\\.\\d+)?[万亿wWkK]?$/.test(line)) return true;
                        if (/^(分享|回复|作者|作者回复过)$/.test(line)) return true;
                        if (/^展开\\d+条回复$/.test(line)) return true;
                        if (/^(今天|昨天|前天|\\d+分钟前|\\d+小时前|\\d+天前|\\d+周前|\\d+月前)(?:·.*)?$/.test(line)) return true;
                        return false;
                    };
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) {
                            return false;
                        }
                        const rect = el.getBoundingClientRect();
                        return rect.width > 30 && rect.height > 20 && rect.bottom > 0 && rect.right > 0;
                    };
                    const panel =
                        panelSelectors
                            .map((selector) => {
                                try {
                                    return document.querySelector(selector);
                                } catch (error) {
                                    return null;
                                }
                            })
                            .find((el) => isVisible(el)) ||
                        null;
                    const root = panel || document.body;
                    const candidates = [];
                    for (const selector of itemSelectors) {
                        let nodes = [];
                        try {
                            nodes = [...root.querySelectorAll(selector)];
                        } catch (error) {
                            continue;
                        }
                        for (const node of nodes) {
                            if (!isVisible(node)) continue;
                            const text = cleanText(node.innerText);
                            if (!text || text.length < 4) continue;
                            const lines = text.split(/\\n+/).map((line) => cleanText(line)).filter(Boolean);
                            if (!lines.length) continue;
                            const contentLines = lines.filter((line) => !isMetaLine(line));
                            const authorLine = contentLines[0] || lines[0] || null;
                            const textLine =
                                contentLines.slice(1).find((line) => line.length >= 2 && line !== authorLine) ||
                                contentLines[1] ||
                                null;
                            if (!textLine) continue;
                            const likeLine = [...lines].reverse().find((line) => /^\\d+(?:\\.\\d+)?[万亿wWkK]?$/.test(line)) || null;
                            candidates.push({
                                author_name: authorLine,
                                text: textLine,
                                like_count_raw: likeLine,
                            });
                            if (candidates.length >= 8) {
                                return candidates;
                            }
                        }
                    }
                    return candidates;
                }""",
                {
                    "panelSelectors": [selector for selector in selectors.COMMENT_PANEL_SELECTORS if ":has-text(" not in selector],
                    "itemSelectors": selectors.COMMENT_ITEM_SELECTORS,
                },
            )
        except Exception as exc:
            self.logger.info(
                "comment ui extraction failed",
                extra={"error_text": str(exc)},
            )
            return [], True
        snippets: list[CommentSnippet] = []
        for item in items or []:
            text = _clean_comment_text((item or {}).get("text"))
            if not text:
                continue
            snippets.append(
                CommentSnippet(
                    author_name=_sanitize_creator_name((item or {}).get("author_name")),
                    text=text,
                    like_count_raw=(item or {}).get("like_count_raw"),
                    source="ui",
                )
            )
        return snippets, False

    def _capture_keyframes(self, debug_label: str | None = None, count: int = 4) -> list[str]:
        if count <= 0:
            return []
        keyframes: list[str] = []
        frame_count = min(max(count, 1), 4)
        for index in range(frame_count):
            label = f"douyin_keyframe_{debug_label}_{index + 1:02d}" if debug_label else f"douyin_keyframe_{index + 1:02d}"
            screenshot_path = self._capture(label)
            if screenshot_path:
                keyframes.append(screenshot_path)
            if index < frame_count - 1:
                self._wait_for_timeout_safe(700, reason=f"keyframe_{index + 1}")
        return keyframes

    def browse_creator_homepage_cycle(self, observation_index: int, debug_label: str | None = None) -> HomepageBrowseResult:
        feed_snapshot = self.observe_interactable_feed(debug_label=debug_label)
        if feed_snapshot.is_live:
            self.logger.info(
                "live feed item detected; skipping homepage open and moving on",
                extra={
                    "observation_index": observation_index,
                    "page_url": feed_snapshot.page_url,
                    "page_title": feed_snapshot.page_title,
                    "feed_identity": feed_snapshot.feed_identity,
                    "active_text_summary": feed_snapshot.active_text_summary,
                },
            )
            return HomepageBrowseResult(
                observation_index=observation_index,
                feed_snapshot=feed_snapshot,
                homepage_open_state="live_skipped",
                homepage_close_state="live_skipped",
            )
        if _looks_like_commerce_feed_item(feed_snapshot.raw_text): #添加商品卡跳过
            self.logger.info(
                "commerce feed item detected; skipping homepage open and moving on",
                extra={
                    "observation_index": observation_index,
                    "creator_name": feed_snapshot.creator_name,
                    "page_url": feed_snapshot.page_url,
                    "page_title": feed_snapshot.page_title,
                    "feed_identity": feed_snapshot.feed_identity,
                    "active_text_summary": feed_snapshot.active_text_summary,
                },
            )
            return HomepageBrowseResult(
                observation_index=observation_index,
                feed_snapshot=feed_snapshot,
                homepage_open_state="commerce_skipped",
                homepage_close_state="commerce_skipped",
            )#
        try:
            homepage_snapshot, screenshot_path = self.open_creator_homepage_with_f(
                observation_index=observation_index,
                debug_label=debug_label,
                candidate=feed_snapshot, # 把当前视频信息 feed_snapshot 传进 open_creator_homepage_with_f()
            )
            profile_snapshot = self.extract_basic_profile_snapshot(feed_snapshot)
            close_snapshot = self.close_creator_homepage_with_f(debug_label=debug_label)
        except (BlockingStateError, PageStructureUncertainError) as exc:
            reason = getattr(exc, "reason", None)
            if reason == BlockReason.PAGE_STRUCTURE_UNCERTAINTY:
                self.logger.info(
                    "f-key did not produce a usable creator profile; skipping directly to next video",
                    extra={
                        "observation_index": observation_index,
                        "page_url": feed_snapshot.page_url,
                        "page_title": feed_snapshot.page_title,
                        "feed_identity": feed_snapshot.feed_identity,
                        "error_message": str(exc),
                    },
                )
                return HomepageBrowseResult(
                    observation_index=observation_index,
                    feed_snapshot=feed_snapshot,
                    homepage_open_state="f_no_effect_skipped",
                    homepage_close_state="f_no_effect_skipped",
                )
            raise
        return HomepageBrowseResult(
            observation_index=observation_index,
            feed_snapshot=feed_snapshot,
            profile_snapshot=profile_snapshot,
            homepage_screenshot_path=screenshot_path,
            homepage_page_url=homepage_snapshot.page_url,
            homepage_page_title=homepage_snapshot.page_title,
            homepage_open_state=homepage_snapshot.state,
            homepage_close_state=close_snapshot.state,
        )

    def analyze_creator(self, candidate: FeedCandidateSnapshot) -> ProfileAnalysisSnapshot:
        self._open_profile(candidate)
        self.raise_for_blockers(page_name="douyin_profile")
        self._pause_before_analysis()

        if not self._looks_like_profile():
            screenshot = self._capture("douyin_profile_structure")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="进入达人主页后未能稳定定位主页结构",
                page_name="douyin_profile",
                screenshot_path=screenshot,
                required_user_action="Please provide a screenshot or DOM snapshot of the Douyin creator profile page.",
            )

        cards = self._collect_video_cards(limit=6)
        if len(cards) < 3:
            screenshot = self._capture("douyin_profile_recent_videos")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="达人主页未能稳定提取最新3条视频数据",
                page_name="douyin_profile",
                screenshot_path=screenshot,
                required_user_action="Please provide a screenshot or DOM snapshot of the recent post grid on this creator profile.",
            )

        recent_cards = [card for card in cards if not card.is_pinned][:3]
        if len(recent_cards) < 3:
            recent_cards = cards[:3]

        recommendation_position = "unknown"
        if candidate.video_url:
            candidate_url = _normalize_url(candidate.video_url)
            for index, card in enumerate(cards):
                if _normalize_url(card.url) == candidate_url:
                    recommendation_position = "pinned" if card.is_pinned or index == 0 else "middle"
                    break

        aggregate_text = " ".join(filter(None, [first_text(self.page, selectors.PROFILE_BIO_SELECTORS), *(card.title or "" for card in recent_cards)]))
        visible_scenes = [scene for scene in ("家庭", "学校", "职场", "户外", "商场", "工作室") if scene in aggregate_text]
        speaking_style = "口播讲解" if any(keyword in aggregate_text for keyword in ("讲解", "测评", "科普")) else None
        duration_pattern = "short_form" if any(re.search(r"\b\d{1,2}:\d{2}\b", (card.title or "")) for card in recent_cards) else None

        return ProfileAnalysisSnapshot(
            creator_name=first_text(self.page, selectors.PROFILE_NAME_SELECTORS) or candidate.creator_name,
            follower_count_raw=_extract_followers(body_text(self.page)),
            total_liked_count_raw=_extract_total_likes(body_text(self.page)),
            profile_bio=first_text(self.page, selectors.PROFILE_BIO_SELECTORS),
            recommendation_video_position=recommendation_position,
            recommendation_video_like_raw=candidate.like_count_raw,
            recent_video_like_raws=[card.like_raw for card in recent_cards[:3]],
            recent_video_titles=[card.title for card in recent_cards if card.title],
            visible_scenes=visible_scenes,
            speaking_style=speaking_style,
            video_duration_pattern=duration_pattern,
            notes=["已执行主页暂停与回顶逻辑"],
        )

    # page.py
    def extract_basic_profile_snapshot(self, candidate: FeedCandidateSnapshot) -> ProfileAnalysisSnapshot:
        panel_text = self._extract_profile_panel_text()
        stats_text = first_text(self.page, selectors.PROFILE_PANEL_STATS_SELECTORS)
        text = panel_text or body_text(self.page)

        creator_name = (
            _extract_profile_panel_name(panel_text)
            or _sanitize_creator_name(candidate.creator_name)
            or _extract_creator_name(text)
        )

        follower_count_raw = _extract_followers(stats_text or "") or _extract_followers(text)
        total_liked_count_raw = _extract_total_likes(stats_text or "") or _extract_total_likes(text)

        # 最新 15 条非置顶作品
        raw_recent_cards = self._collect_video_cards(limit=40)
        raw_recent_cards = [card for card in raw_recent_cards if not card.is_pinned] or raw_recent_cards
        
        recent_cards = _compact_profile_video_cards(
            raw_recent_cards,
            limit=15,
            total_liked_count_raw=total_liked_count_raw,
        )

        self.logger.info(
            "profile recent works extracted",
            extra={
                "creator_name": creator_name,
                "recent_work_count": len(recent_cards),
                "recent_like_raws": [card.like_raw for card in recent_cards],
                "recent_titles": [card.title for card in recent_cards],
            },
        )


        return ProfileAnalysisSnapshot(
            creator_name=creator_name,
            follower_count_raw=follower_count_raw,
            total_liked_count_raw=total_liked_count_raw,
            profile_bio=first_text(self.page, selectors.PROFILE_BIO_SELECTORS),
            recommendation_video_like_raw=candidate.like_count_raw,
            recent_video_like_raws=[card.like_raw for card in recent_cards],
            recent_video_titles=[card.title for card in recent_cards],
            visible_scenes=[],
            notes=[
                "已执行最小主页抓取流程",
                f"profile_recent_work_count={len(recent_cards)}",
            ],
        )
    def _extract_profile_panel_text(self) -> str | None:
        try:
            panel_text = self.page.evaluate(
                """() => {
                    const elements = [...document.querySelectorAll('body *')];
                    const candidates = elements
                        .map((el) => {
                            const text = (el.innerText || '').trim();
                            const rect = el.getBoundingClientRect();
                            return {
                                text,
                                left: rect.left,
                                top: rect.top,
                                width: rect.width,
                                height: rect.height,
                            };
                        })
                        .filter((item) =>
                            item.text &&
                            item.text.includes('粉丝') &&
                            item.text.includes('获赞') &&
                            item.left >= window.innerWidth * 0.65 &&
                            item.width >= 80 &&
                            item.height >= 30
                        )
                        .sort((a, b) => {
                            const areaA = a.width * a.height;
                            const areaB = b.width * b.height;
                            if (a.top !== b.top) return a.top - b.top;
                            return areaA - areaB;
                        });
                    return candidates[0]?.text || null;
                }"""
            )
        except Exception:
            return None
        if not panel_text:
            return None
        cleaned = panel_text.strip()
        return cleaned or None

    def open_creator_homepage_with_f( # modified
        self,
        observation_index: int,
        debug_label: str | None = None,
        candidate: FeedCandidateSnapshot | None = None,#modified
    ) -> tuple[PageStateSnapshot, str | None]:
        preflight = self.classify_page_state(
            debug_label=f"{debug_label}_homepage_preflight" if debug_label else "homepage_preflight",
            capture=False,
        )
        if preflight.state == "live_room_open":
            if not self._recover_from_live_room(preflight):
                raise self._snapshot_to_blocking_error(preflight, page_name="douyin_creator_homepage_open")
            preflight = self.classify_page_state(
                debug_label=f"{debug_label}_homepage_preflight_recovered" if debug_label else "homepage_preflight_recovered",
                capture=False,
            )
        if preflight.state == "self_profile_open":
            if not self._recover_from_self_profile(debug_label=f"{debug_label}_homepage_preflight" if debug_label else "homepage_preflight"):
                raise self._snapshot_to_blocking_error(preflight, page_name="douyin_creator_homepage_open")
            preflight = self.classify_page_state(
                debug_label=f"{debug_label}_homepage_preflight_self_recovered" if debug_label else "homepage_preflight_self_recovered",
                capture=False,
            )
        if preflight.state == "creator_homepage_open":
            screenshot_label = (
                f"douyin_creator_homepage_obs_{observation_index:03d}_{debug_label}"
                if debug_label
                else f"douyin_creator_homepage_obs_{observation_index:03d}"
            )
            screenshot_path = self._capture(screenshot_label)
            self.logger.info(
                "creator homepage already open before pressing f",
                extra={
                    "observation_index": observation_index,
                    "page_url": preflight.page_url,
                    "page_title": preflight.page_title,
                    "screenshot_path": screenshot_path,
                },
            )
            return preflight, screenshot_path
        if preflight.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            raise self._snapshot_to_blocking_error(preflight, page_name="douyin_creator_homepage_open")
        state = self._extract_active_feed_state()
        if state is None:
            snapshot = self.classify_page_state(debug_label=f"{debug_label}_homepage_open_gate" if debug_label else "homepage_open_gate", capture=True)
            if snapshot.state == "live_room_open" and self._recover_from_live_room(snapshot):
                snapshot = self.classify_page_state(
                    debug_label=f"{debug_label}_homepage_open_gate_recovered" if debug_label else "homepage_open_gate_recovered",
                    capture=True,
                )
            if snapshot.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_creator_homepage_open")
            self._focus_feed_shell()
        else:
            self._focus_active_feed(state)
        #modified
        creator_profile_url = _normalize_url(
            (state or {}).get("creator_profile_url")
            or (candidate.creator_profile_url if candidate else None)
        )

        if not creator_profile_url:
            screenshot = self._capture(
                f"douyin_creator_homepage_no_author_link_{debug_label}" if debug_label else "douyin_creator_homepage_no_author_link"
            ) #modified
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="当前激活推荐卡片缺少达人主页链接，跳过 F 键主页打开，避免误入我的主页。",
                page_name="douyin_creator_homepage_open",
                screenshot_path=screenshot,
                required_user_action="Please scroll to a stable active video card where the author link is visible, then retry.",
                resumable=True,
            )
        current_snapshot = self.classify_page_state(
            debug_label=f"{debug_label}_homepage_before_press" if debug_label else "homepage_before_press",
            capture=False,
        )
        if current_snapshot.state == "live_room_open":
            if not self._recover_from_live_room(current_snapshot):
                raise self._snapshot_to_blocking_error(current_snapshot, page_name="douyin_creator_homepage_open")
            current_snapshot = self.classify_page_state(
                debug_label=f"{debug_label}_homepage_before_press_recovered" if debug_label else "homepage_before_press_recovered",
                capture=False,
            )
        if current_snapshot.state == "self_profile_open":
            if not self._recover_from_self_profile(debug_label=f"{debug_label}_homepage_before_press" if debug_label else "homepage_before_press"):
                raise self._snapshot_to_blocking_error(current_snapshot, page_name="douyin_creator_homepage_open")
            current_snapshot = self.classify_page_state(
                debug_label=f"{debug_label}_homepage_before_press_self_recovered" if debug_label else "homepage_before_press_self_recovered",
                capture=False,
            )
        if current_snapshot.state == "creator_homepage_open":
            screenshot_label = (
                f"douyin_creator_homepage_obs_{observation_index:03d}_{debug_label}"
                if debug_label
                else f"douyin_creator_homepage_obs_{observation_index:03d}"
            )
            screenshot_path = self._capture(screenshot_label)
            self.logger.info(
                "creator homepage already open right before pressing f",
                extra={
                    "observation_index": observation_index,
                    "page_url": current_snapshot.page_url,
                    "page_title": current_snapshot.page_title,
                    "screenshot_path": screenshot_path,
                },
            )
            return current_snapshot, screenshot_path
        if current_snapshot.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            raise self._snapshot_to_blocking_error(current_snapshot, page_name="douyin_creator_homepage_open")
        previous_url = self.page.url
        #不要在直播里按F
        if "/root/live/" in (self.page.url or ""):
            self.logger.warning(
                "skip F-key homepage open because current page is live room",
                extra={
                    "debug_label": debug_label,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )

            try:
                self.page.goto(
                    "https://www.douyin.com/?recommend=1",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                self.page.wait_for_timeout(1500)
            except Exception:
                pass

            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="当前页面是直播间，跳过 F 键主页打开，避免卡在直播页面。",
                page_name="douyin_live_room",
                page_state="live_room_before_f_key",
                required_user_action="No manual action needed. The workflow should skip this live item and move to the next video.",
                needs_user_action=False,
                resumable=True,
            )
        self.logger.info(
            "pressing f to open creator homepage",
            extra={
                "observation_index": observation_index,
                "page_url": previous_url,
                "page_title": self._safe_title(),
                "feed_identity": _state_identity(state),
            },
        )
        self._prepare_feed_focus_before_homepage_open(debug_label=debug_label) # 在按 F 之前，先清理页面焦点。
        self.page.keyboard.press("f")
        snapshot = self._wait_for_creator_homepage_state(opening=True, previous_url=previous_url, debug_label=debug_label)
        # 修改方法3: 如果 F 没成功，但手里有 creator_profile_url，就直接 page.goto(达人主页链接)，再重新判断页面状态
        if snapshot.state != "creator_homepage_open" and creator_profile_url:
            self.logger.info(
                "F-key homepage entry failed after overlay cleanup; trying direct creator profile URL",
                extra={
                    "creator_profile_url": creator_profile_url,
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "debug_label": debug_label,
                },
            )

            self.page.goto(
                creator_profile_url,
                wait_until="domcontentloaded",
                timeout=45_000,
            )
            self.page.wait_for_timeout(1_500)

            snapshot = self.classify_page_state(
                debug_label=f"{debug_label}_homepage_direct_url" if debug_label else "homepage_direct_url",
                capture=True,
            )
        # 修改方法3结束
        if snapshot.state == "self_profile_open":
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="F 键误入我的主页，未打开当前推荐视频作者主页。",
                page_name="douyin_creator_homepage_open",
                screenshot_path=snapshot.screenshot_path,
                required_user_action="Please return to the recommend feed and ensure the active card is focused before retrying.",
                resumable=True,
            )
        screenshot_label = (
            f"douyin_creator_homepage_obs_{observation_index:03d}_{debug_label}"
            if debug_label
            else f"douyin_creator_homepage_obs_{observation_index:03d}"
        )
        screenshot_path = self._capture(screenshot_label)
        self.logger.info(
            "creator homepage screenshot saved",
            extra={
                "observation_index": observation_index,
                "page_url": snapshot.page_url,
                "page_title": snapshot.page_title,
                "screenshot_path": screenshot_path,
            },
        )
        return snapshot, screenshot_path

    def close_creator_homepage_with_f(self, debug_label: str | None = None) -> PageStateSnapshot:
        snapshot = self.classify_page_state(debug_label=f"{debug_label}_homepage_close_gate" if debug_label else "homepage_close_gate", capture=True)
        if snapshot.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            return PageStateSnapshot(
                state="creator_homepage_closed_returned",
                page_url=snapshot.page_url,
                page_title=snapshot.page_title,
                visible_text_summary=snapshot.visible_text_summary,
                reason="当前已处于推荐流视图。",
            )
        if snapshot.state == "self_profile_open":
            if self._recover_from_self_profile(debug_label=debug_label):
                returned_snapshot = self.classify_page_state(
                    debug_label=f"{debug_label}_self_profile_recovered" if debug_label else "self_profile_recovered",
                    capture=True,
                )
                return PageStateSnapshot(
                    state="creator_homepage_closed_returned",
                    page_url=returned_snapshot.page_url,
                    page_title=returned_snapshot.page_title,
                    visible_text_summary=returned_snapshot.visible_text_summary,
                    reason="误入我的主页后已返回推荐流。",
                )
            raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_creator_homepage_close")
        if snapshot.state != "creator_homepage_open":
            raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_creator_homepage_close")

        previous_url = self.page.url
        self.logger.info(
            "pressing f to return to feed",
            extra={
                "page_url": previous_url,
                "page_title": self._safe_title(),
            },
        )
        self.page.keyboard.press("f")
        returned_snapshot = self._wait_for_creator_homepage_state(opening=False, previous_url=previous_url, debug_label=debug_label)
        self.logger.info(
            "returned to feed after homepage view",
            extra={
                "page_url": returned_snapshot.page_url,
                "page_title": returned_snapshot.page_title,
                "page_state": returned_snapshot.state,
            },
        )
        return PageStateSnapshot(
            state="creator_homepage_closed_returned",
            page_url=returned_snapshot.page_url,
            page_title=returned_snapshot.page_title,
            visible_text_summary=returned_snapshot.visible_text_summary,
            reason="已通过 F 键返回推荐流。",
        )

    def return_to_feed(self) -> None:
        page_state = self.classify_page_state(debug_label="return_to_feed", capture=False)
        if page_state.state == "live_room_open":
            if self._recover_from_live_room(page_state):
                return
        if page_state.state == "self_profile_open":
            if self._recover_from_self_profile(debug_label="return_to_feed"):
                return
        if page_state.state == "creator_homepage_open":
            try:
                self.close_creator_homepage_with_f(debug_label="return_to_feed")
                return
            except Exception:
                pass
        if page_state.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            return
        back_button = first_visible_locator(self.page, selectors.RETURN_TO_FEED_SELECTORS)
        if back_button is not None:
            try:
                back_button.click(timeout=1_000)
                self.page.wait_for_timeout(900)
                if self._extract_active_feed_state() is not None:
                    return
            except Exception:
                pass
        try:
            self.page.go_back(wait_until="domcontentloaded")
            self.page.wait_for_timeout(1500)
            if self._extract_active_feed_state() is not None:
                return
        except Exception:
            pass
        self.page.goto(selectors.BASE_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1_000)
        self._enter_recommendation_feed()

    def advance_feed(
        self,
        previous_candidate: FeedCandidateSnapshot | None = None,
        debug_label: str | None = None,
    ) -> FeedAdvanceResult:
        self._dismiss_login_modal(reason="advance_feed_preflight", debug_label=debug_label)
        self._dismiss_feed_side_panel(reason="advance_feed_preflight", debug_label=debug_label)
        page_state = self.classify_page_state(debug_label=debug_label)
        for remediation_attempt in range(2):
            if page_state.state == "self_profile_open":
                try:
                    self.logger.info(
                        "advance feed encountered self profile; returning to recommend feed first",
                        extra={
                            "page_url": page_state.page_url,
                            "page_title": page_state.page_title,
                            "debug_label": debug_label,
                            "remediation_attempt": remediation_attempt + 1,
                        },
                    )
                    self._recover_from_self_profile(debug_label=debug_label)
                except Exception:
                    break
                page_state = self.classify_page_state(debug_label=f"{debug_label}_post_self_profile_recovery" if debug_label else None)
                continue
            if page_state.state == "creator_homepage_open":
                try:
                    self.logger.info(
                        "advance feed encountered lingering creator homepage; returning to feed first",
                        extra={
                            "page_url": page_state.page_url,
                            "page_title": page_state.page_title,
                            "debug_label": debug_label,
                            "remediation_attempt": remediation_attempt + 1,
                        },
                    )
                    self.close_creator_homepage_with_f(debug_label=debug_label)
                except Exception:
                    break
                page_state = self.classify_page_state(debug_label=f"{debug_label}_post_homepage_close" if debug_label else None)
                continue
            if page_state.state == "live_room_open":
                if not self._recover_from_live_room(page_state):
                    break
                page_state = self.classify_page_state(debug_label=f"{debug_label}_post_live_recovery" if debug_label else None)
                continue
            break
        if page_state.state not in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
            return FeedAdvanceResult(
                changed=False,
                before_identity=self._candidate_identity(previous_candidate),
                after_identity=None,
                before_summary=previous_candidate.active_text_summary if previous_candidate else None,
                after_summary=page_state.visible_text_summary,
                page_url=page_state.page_url,
                page_title=page_state.page_title,
                screenshot_path=page_state.screenshot_path,
                debug_label=f"{debug_label}|state={page_state.state}" if debug_label else f"state={page_state.state}",
            )
        before_state = self._extract_active_feed_state()
        previous_identity = self._candidate_identity(previous_candidate) or _state_identity(before_state)
        before_summary = (
            previous_candidate.active_text_summary
            if previous_candidate is not None
            else _summarize_text((before_state or {}).get("active_text"))
        )
        if self._click_next_feed_arrow(debug_label=debug_label, reason="advance_feed"):
            post_click_state = self.classify_page_state(debug_label=f"{debug_label}_after_right_arrow" if debug_label else None)
            if post_click_state.state == "live_room_open":
                self.logger.info(
                    "right-arrow navigation entered live room; recovering and trying fallback movement",
                    extra={
                        "page_url": post_click_state.page_url,
                        "page_title": post_click_state.page_title,
                        "debug_label": debug_label,
                    },
                )
                if self._recover_from_live_room(post_click_state):
                    page_state = self.classify_page_state(debug_label=f"{debug_label}_after_live_recovery" if debug_label else None)
                    if page_state.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                        before_state = self._extract_active_feed_state()
                        previous_identity = self._candidate_identity(previous_candidate) or _state_identity(before_state)
                        before_summary = (
                            previous_candidate.active_text_summary
                            if previous_candidate is not None
                            else _summarize_text((before_state or {}).get("active_text"))
                        )
                else:
                    return FeedAdvanceResult(
                        changed=False,
                        before_identity=previous_identity,
                        after_identity=None,
                        before_summary=before_summary,
                        after_summary=post_click_state.visible_text_summary,
                        page_url=post_click_state.page_url,
                        page_title=post_click_state.page_title,
                        screenshot_path=post_click_state.screenshot_path,
                        debug_label=f"{debug_label}|state=live_room_open" if debug_label else "state=live_room_open",
                    )
            elif post_click_state.state == "creator_homepage_open":
                try:
                    self.close_creator_homepage_with_f(debug_label=debug_label)
                except Exception:
                    pass
            after_candidate = self._collect_feed_snapshot(active_state=self._extract_active_feed_state())
            after_identity = self._candidate_identity(after_candidate)
            after_summary = after_candidate.active_text_summary or _summarize_text(body_text(self.page))
            if _feed_identity_changed(previous_identity, after_identity, before_summary, after_summary):
                screenshot_path = self._capture(
                    f"douyin_feed_after_scroll_{debug_label}" if debug_label else "douyin_feed_after_scroll"
                )
                return FeedAdvanceResult(
                    changed=True,
                    before_identity=previous_identity,
                    after_identity=after_identity,
                    before_summary=before_summary,
                    after_summary=after_summary,
                    page_url=self.page.url,
                    page_title=self._safe_title(),
                    screenshot_path=screenshot_path,
                    debug_label=f"{debug_label}|method=right_arrow" if debug_label else "method=right_arrow",
                )
        wheel_distances = (1_250, 1_450, 1_700)
        for distance in wheel_distances:
            self.logger.info(
                "scrolling to next video",
                extra={
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "wheel_distance": distance,
                    "debug_label": debug_label,
                },
            )
            self.page.mouse.wheel(0, distance)
            if not self._wait_for_timeout_safe(1_000, reason=f"advance_feed_wheel_{distance}"):
                break
            wheel_state = self.classify_page_state(debug_label=f"{debug_label}_after_wheel_{distance}" if debug_label else None)
            if wheel_state.state == "live_room_open":
                self.logger.info(
                    "wheel navigation entered live room; recovering and continuing feed advance",
                    extra={
                        "page_url": wheel_state.page_url,
                        "page_title": wheel_state.page_title,
                        "wheel_distance": distance,
                        "debug_label": debug_label,
                    },
                )
                if self._recover_from_live_room(wheel_state):
                    continue
                return FeedAdvanceResult(
                    changed=False,
                    before_identity=previous_identity,
                    after_identity=None,
                    before_summary=before_summary,
                    after_summary=wheel_state.visible_text_summary,
                    page_url=wheel_state.page_url,
                    page_title=wheel_state.page_title,
                    screenshot_path=wheel_state.screenshot_path,
                    debug_label=f"{debug_label}|state=live_room_open" if debug_label else "state=live_room_open",
                )
            after_candidate = self._collect_feed_snapshot(active_state=self._extract_active_feed_state())
            after_identity = self._candidate_identity(after_candidate)
            after_summary = after_candidate.active_text_summary or _summarize_text(body_text(self.page))
            if _feed_identity_changed(previous_identity, after_identity, before_summary, after_summary):
                screenshot_path = self._capture(
                    f"douyin_feed_after_scroll_{debug_label}" if debug_label else "douyin_feed_after_scroll"
                )
                return FeedAdvanceResult(
                    changed=True,
                    before_identity=previous_identity,
                    after_identity=after_identity,
                    before_summary=before_summary,
                    after_summary=after_summary,
                    page_url=self.page.url,
                    page_title=self._safe_title(),
                    screenshot_path=screenshot_path,
                    debug_label=debug_label,
                )
        self.logger.info(
            "scrolling to next video",
            extra={
                "page_url": self.page.url,
                "page_title": self._safe_title(),
                "method": "PageDown",
                "debug_label": debug_label,
            },
        )
        self.page.keyboard.press("PageDown")
        self._wait_for_timeout_safe(1_100, reason="advance_feed_pagedown")
        pagedown_state = self.classify_page_state(debug_label=f"{debug_label}_after_pagedown" if debug_label else None)
        if pagedown_state.state == "live_room_open":
            if self._recover_from_live_room(pagedown_state):
                pagedown_state = self.classify_page_state(debug_label=f"{debug_label}_post_pagedown_live_recovery" if debug_label else None)
        after_candidate = self._collect_feed_snapshot(active_state=self._extract_active_feed_state())
        after_identity = self._candidate_identity(after_candidate)
        after_summary = after_candidate.active_text_summary or _summarize_text(body_text(self.page))
        screenshot_path = self._capture(
            f"douyin_feed_after_scroll_{debug_label}" if debug_label else "douyin_feed_after_scroll"
        )
        changed = _feed_identity_changed(previous_identity, after_identity, before_summary, after_summary)
        if not changed:
            try:
                if self._goto_recommend_route_for_repair():
                    refreshed_state = self.classify_page_state(
                        debug_label=f"{debug_label}_after_direct_recommend_repair" if debug_label else "after_direct_recommend_repair",
                        capture=False,
                    )
                    if refreshed_state.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                        self._wheel_feed_surface(1200, reason="advance_feed_direct_recommend_wheel")
                        repaired_candidate = self._collect_feed_snapshot(active_state=self._extract_active_feed_state())
                        repaired_identity = self._candidate_identity(repaired_candidate)
                        repaired_summary = repaired_candidate.active_text_summary or _summarize_text(body_text(self.page))
                        if _feed_identity_changed(previous_identity, repaired_identity, before_summary, repaired_summary):
                            repaired_screenshot = self._capture(
                                f"douyin_feed_after_scroll_direct_recommend_{debug_label}"
                                if debug_label
                                else "douyin_feed_after_scroll_direct_recommend"
                            )
                            return FeedAdvanceResult(
                                changed=True,
                                before_identity=previous_identity,
                                after_identity=repaired_identity,
                                before_summary=before_summary,
                                after_summary=repaired_summary,
                                page_url=self.page.url,
                                page_title=self._safe_title(),
                                screenshot_path=repaired_screenshot,
                                debug_label=f"{debug_label}|method=direct_recommend_repair" if debug_label else "method=direct_recommend_repair",
                            )
            except Exception as exc:
                self.logger.info(
                    "direct recommend fallback did not advance feed",
                    extra={
                        "page_url": self.page.url if self.page and not self.page.is_closed() else None,
                        "page_title": self._safe_title(),
                        "debug_label": debug_label,
                        "error_text": str(exc),
                    },
                )
        return FeedAdvanceResult(
            changed=changed,
            before_identity=previous_identity,
            after_identity=after_identity,
            before_summary=before_summary,
            after_summary=after_summary,
            page_url=self.page.url,
            page_title=self._safe_title(),
            screenshot_path=screenshot_path,
            debug_label=debug_label,
        )

    def _open_profile(self, candidate: FeedCandidateSnapshot) -> None:
        state = self._extract_active_feed_state()
        if state is None:
            screenshot = self._capture("douyin_profile_open_failed")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="进入主页前未能识别当前激活的推荐视频区域",
                page_name="douyin_feed",
                screenshot_path=screenshot,
                required_user_action="Please provide a screenshot or DOM snapshot of the active Douyin recommendation video state.",
            )
        current_identity = _state_identity(state)
        if (
            candidate.creator_profile_url
            and candidate.feed_identity
            and current_identity
            and current_identity != candidate.feed_identity
        ):
            try:
                self.logger.info(
                    "active feed drifted before homepage entry; using creator URL fallback",
                    extra={
                        "candidate_feed_identity": candidate.feed_identity,
                        "current_feed_identity": current_identity,
                        "creator_profile_url": candidate.creator_profile_url,
                    },
                )
                self.page.goto(candidate.creator_profile_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(1_200)
                self.raise_for_blockers(page_name="douyin_profile")
                if self._looks_like_profile():
                    return
            except BlockingStateError:
                raise
            except Exception:
                pass
        self._focus_active_feed(state)
        previous_url = self.page.url
        self.page.locator("body").press("f")
        if self._wait_for_profile_entry(previous_url):
            return
        if candidate.creator_profile_url:
            try:
                self.logger.info("F-key homepage entry did not stabilize; trying direct creator URL fallback")
                self.page.goto(candidate.creator_profile_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(1_200)
                self.raise_for_blockers(page_name="douyin_profile")
                if self._looks_like_profile():
                    return
            except BlockingStateError:
                raise
            except Exception:
                pass
        screenshot = self._capture("douyin_profile_open_failed")
        raise PageStructureUncertainError(
            reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            message="已尝试通过 F 键进入达人主页，但页面未稳定进入主页态",
            page_name="douyin_feed",
            screenshot_path=screenshot,
            required_user_action="Please provide the screenshot or DOM snapshot right after pressing F on the active Douyin feed item.",
        )

    def _pause_before_analysis(self) -> None:
        pause_button = first_visible_locator(self.page, selectors.PAUSE_BUTTON_SELECTORS)
        if pause_button is not None:
            try:
                pause_button.click(timeout=800)
            except Exception:
                self.page.keyboard.press("Space")
        else:
            self.page.keyboard.press("Space")
        self.page.wait_for_timeout(500)
        self.page.mouse.wheel(0, -1_600)
        self.page.wait_for_timeout(500)

    def _prompt_for_manual_resolution(self, snapshot: PageStateSnapshot, bootstrap_login: bool) -> bool:
        if not sys.stdin.isatty():
            return False
        action_hint = {
            "unauthenticated": "Please log into Douyin in the opened browser window.",
            "login_modal": "Please complete the Douyin login modal in the opened browser window.",
            "captcha_blocked": "Please complete the Douyin captcha / slider verification in the opened browser window.",
            "abnormal/footer/download_page": (
                "Please dismiss any open-app / download-app / xdg-open style interruption and return to the normal Douyin web page."
            ),
        }.get(snapshot.state, "Please restore the Douyin page to a usable state.")
        bootstrap_hint = "bootstrap session" if bootstrap_login else "discovery session"
        prompt = (
            f"\nDouyin {bootstrap_hint} is paused.\n"
            f"Page state: {snapshot.state}\n"
            f"Reason: {snapshot.reason}\n"
            f"{action_hint}\n"
            "After the page is back to the normal Douyin web experience, press Enter here to continue..."
        )
        self.logger.warning(
            "douyin needs user action",
            extra={
                "page_state": snapshot.state,
                "page_url": snapshot.page_url,
                "page_title": snapshot.page_title,
                "reason": snapshot.reason,
                "detected_phrase": snapshot.detected_phrase,
                "bootstrap_login": bootstrap_login,
                "screenshot_path": snapshot.screenshot_path,
            },
        )
        print(prompt, flush=True)
        try:
            input()
        except EOFError:
            return False
        self.page.wait_for_timeout(1_200)
        return True

    def _recover_from_blocking_ui(self, snapshot: PageStateSnapshot) -> bool:
        if snapshot.state != "abnormal/footer/download_page":
            return False
        if not self._ensure_page_open(goto_base=False, reason="recover_from_blocking_ui"):
            return False
        if snapshot.detected_phrase:
            self.logger.warning(
                "douyin blocking ui detected",
                extra={
                    "detected_phrase": snapshot.detected_phrase,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                },
            )
        try:
            self.page.keyboard.press("Escape")
            if not self._wait_for_timeout_safe(500, reason="dismiss_blocking_ui_escape"):
                return False
        except Exception:
            pass
        for selector in selectors.BLOCKING_UI_DISMISS_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=300)
            if locator is None:
                continue
            try:
                locator.click(timeout=600)
                if not self._wait_for_timeout_safe(700, reason=f"dismiss_blocking_ui:{selector}"):
                    return False
                new_state = self.classify_page_state()
                if new_state.state != "abnormal/footer/download_page":
                    self.logger.info(
                        "douyin blocking ui dismissed",
                        extra={"selector": selector, "new_state": new_state.state},
                    )
                    return True
            except Exception:
                continue
        if snapshot.blocking_reason == BlockReason.EXTERNAL_APP_INTERRUPTION:
            self.logger.info(
                "douyin blocking ui recovery retrying root navigation",
                extra={
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "detected_phrase": snapshot.detected_phrase,
                },
            )
            try:
                self.page.goto(selectors.BASE_URL, wait_until="domcontentloaded", timeout=25_000)
                if not self._wait_for_timeout_safe(1_000, reason="blocking_ui_root_recovery"):
                    return False
                new_state = self.classify_page_state(debug_label="post_blocking_ui_recovery", capture=True)
                if new_state.state != "abnormal/footer/download_page":
                    self.logger.info(
                        "douyin blocking ui recovered after root navigation",
                        extra={
                            "new_state": new_state.state,
                            "page_url": new_state.page_url,
                            "page_title": new_state.page_title,
                            "screenshot_path": new_state.screenshot_path,
                        },
                    )
                    return True
            except Exception as exc:
                self.logger.warning("douyin root navigation recovery failed: %s", exc)
        return False

    def _recover_from_live_room(self, snapshot: PageStateSnapshot | None = None) -> bool:
        if not self._ensure_page_open(goto_base=False, reason="recover_from_live_room"):
            return False
        self.logger.warning(
            "douyin live room detected; attempting to return to recommend feed",
            extra={
                "page_url": (snapshot.page_url if snapshot else self.page.url),
                "page_title": (snapshot.page_title if snapshot else self._safe_title()),
                "detected_phrase": snapshot.detected_phrase if snapshot else None,
            },
        )
        for selector in selectors.LIVE_ROOM_BACK_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=220)
            if locator is None:
                continue
            try:
                locator.click(timeout=450)
                if self._wait_for_timeout_safe(450, reason=f"live_room_back:{selector}"):
                    refreshed = self.classify_page_state(debug_label="post_live_back_selector", capture=False)
                    if refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}:
                        return True
                break
            except Exception:
                continue
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        for point in ((24, 24), (36, 36), (52, 24)):
            try:
                self.page.mouse.click(*point)
                if self._wait_for_timeout_safe(400, reason="live_room_top_left_back"):
                    refreshed = self.classify_page_state(debug_label="post_live_top_left_back", capture=False)
                    if refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}:
                        return True
            except Exception:
                continue
        try:
            self.page.keyboard.press("Escape")
            if self._wait_for_timeout_safe(400, reason="live_room_escape"):
                refreshed = self.classify_page_state(debug_label="post_live_escape", capture=False)
                if refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}:
                    return True
        except Exception:
            pass
        for selector in selectors.LIVE_ROOM_EXIT_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=250)
            if locator is None:
                continue
            try:
                locator.click(timeout=600)
                if self._wait_for_timeout_safe(700, reason=f"live_room_exit:{selector}"):
                    refreshed = self.classify_page_state(debug_label="post_live_exit", capture=False)
                    if refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}:
                        return True
            except Exception:
                continue
        try:
            self.page.go_back(wait_until="domcontentloaded", timeout=6_000)
            if self._wait_for_timeout_safe(650, reason="live_room_go_back"):
                refreshed = self.classify_page_state(debug_label="post_live_go_back", capture=False)
                if refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}:
                    return True
        except Exception:
            pass
        try:
            self.page.goto("https://www.douyin.com/?recommend=1&from_nav=1", wait_until="domcontentloaded", timeout=25_000)
            if self._wait_for_timeout_safe(1_200, reason="live_room_goto_recommend"):
                refreshed = self.classify_page_state(debug_label="post_live_recommend_goto", capture=False)
                return refreshed.state in {"recommend_feed_interactable", "recommended_feed_ready", "recommend_feed_shell"}
        except Exception:
            pass
        return False

    def _click_next_feed_arrow(self, debug_label: str | None = None, reason: str = "advance_feed") -> bool:
        if not self._ensure_page_open(goto_base=False, reason=f"click_next_feed_arrow:{reason}"):
            return False
        self._dismiss_login_modal(reason=reason, debug_label=debug_label)
        self._dismiss_feed_side_panel(reason=reason, debug_label=debug_label)
        self._dismiss_recommend_feed_ack(reason=reason)
        for selector in selectors.NEXT_VIDEO_BUTTON_SELECTORS:
            try:
                locator = self.page.locator(selector).first
                if not locator.count() or not locator.is_visible(timeout=450):
                    continue
                try:
                    locator.scroll_into_view_if_needed(timeout=450)
                except Exception:
                    pass
                self.logger.info(
                    "clicking right-side down arrow to move to next video",
                    extra={
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                        "debug_label": debug_label,
                        "reason": reason,
                        "target_strategy": "selector",
                        "target_selector": selector,
                    },
                )
                try:
                    locator.click(timeout=900)
                except Exception:
                    locator.click(timeout=900, force=True)
                if self._wait_for_timeout_safe(1_050, reason=f"next_button_selector_click:{reason}"):
                    return True
            except Exception:
                continue
        targets = [self._locate_fixed_right_side_down_arrow(), self._locate_right_side_down_arrow()]
        for target in targets:
            if target is None:
                continue
            self.logger.info(
                "clicking right-side down arrow to move to next video",
                extra={
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                    "debug_label": debug_label,
                    "reason": reason,
                    "target_x": target["x"],
                    "target_y": target["y"],
                    "target_width": target["width"],
                    "target_height": target["height"],
                    "target_tag": target["tag"],
                    "target_strategy": target.get("strategy"),
                    "target_text": target.get("text"),
                },
            )
            try:
                self.page.mouse.click(target["x"], target["y"])
            except Exception:
                continue
            if self._wait_for_timeout_safe(1_050, reason=f"right_arrow_click:{reason}"):
                return True
        return False

    def _dismiss_recommend_feed_ack(self, reason: str) -> bool:
        locator = first_visible_locator(self.page, selectors.FEED_ACK_BUTTON_SELECTORS, timeout_ms=300)
        if locator is None:
            return False
        self.logger.info(
            "dismissing recommend feed acknowledgement",
            extra={
                "page_url": self.page.url,
                "page_title": self._safe_title(),
                "reason": reason,
            },
        )
        try:
            locator.click(timeout=700)
        except Exception:
            try:
                locator.click(timeout=700, force=True)
            except Exception:
                return False
        return self._wait_for_timeout_safe(500, reason=f"dismiss_feed_ack:{reason}")

    def _locate_fixed_right_side_down_arrow(self) -> dict[str, int | str] | None:
        try:
            target = self.page.evaluate(
                """() => {
                    const width = window.innerWidth || document.documentElement.clientWidth || 0;
                    const height = window.innerHeight || document.documentElement.clientHeight || 0;
                    if (width < 320 || height < 320) return null;
                    const x = Math.max(24, Math.round(width - Math.min(44, width * 0.03)));
                    const y = Math.max(24, Math.min(height - 24, Math.round(height * 0.74)));
                    const el = document.elementFromPoint(x, y);
	                    const rect = el && typeof el.getBoundingClientRect === 'function'
	                        ? el.getBoundingClientRect()
	                        : {width: 0, height: 0};
	                    const text = el ? ((el.innerText || el.textContent || '')).trim().slice(0, 60) : '';
	                    if (rect.width > 140 || rect.height > 160) return null;
	                    if (text && !/^[↓∨⌄⌵]$/.test(text)) return null;
	                    return {
                        x,
                        y,
                        width: Math.round(rect.width || 0),
                        height: Math.round(rect.height || 0),
                        tag: el ? String(el.tagName || '').toLowerCase() || 'viewport' : 'viewport',
                        text,
                        strategy: 'fixed_viewport',
                    };
                }"""
            )
        except Exception:
            return None
        if not isinstance(target, dict):
            return None
        return target

    def _locate_right_side_down_arrow(self) -> dict[str, int | str] | None:
        try:
            target = self.page.evaluate(
                """() => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width >= 20 && rect.height >= 20 && rect.bottom > 0 && rect.right > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth;
                    };
                    const clickable = (el) => {
                        if (!el) return false;
                        const role = (el.getAttribute('role') || '').toLowerCase();
                        return el.tagName === 'BUTTON' || el.tagName === 'A' || role === 'button' || typeof el.onclick === 'function';
                    };
                    const candidates = [];
                    const seen = new Set();
                    const nodes = document.querySelectorAll('button, a, div, [role=\"button\"]');
                    for (const el of nodes) {
                        if (seen.has(el) || !isVisible(el)) continue;
                        seen.add(el);
                        const rect = el.getBoundingClientRect();
                        if (rect.left < window.innerWidth * 0.86) continue;
                        if (rect.top < window.innerHeight * 0.55 || rect.bottom > window.innerHeight - 20) continue;
                        if (rect.width > 120 || rect.height > 220) continue;
                        const svgCount = el.querySelectorAll('svg').length + (el.tagName === 'svg' ? 1 : 0);
                        const text = ((el.innerText || el.textContent || '')).trim();
                        const childButtons = el.querySelectorAll('button, [role=\"button\"]').length;
                        const rightness = rect.left / window.innerWidth;
                        const verticalBias = 1 - Math.abs((rect.top + rect.height / 2) - window.innerHeight * 0.76) / window.innerHeight;
                        let score = rightness * 10 + verticalBias * 8 + Math.min(svgCount, 3) * 3 + Math.min(childButtons, 2) * 2;
                        if (clickable(el)) score += 3;
                        if (!text) score += 2;
                        if (svgCount >= 2 && rect.height >= 60) score += 4;
                        if (text && /赞|评|收藏|分享|AI/.test(text)) score -= 8;
                        candidates.push({
                            score,
                            rect: {left: rect.left, top: rect.top, width: rect.width, height: rect.height},
                            tag: el.tagName.toLowerCase(),
                            svgCount,
                            text,
                        });
                    }
                    candidates.sort((a, b) => b.score - a.score);
                    const best = candidates[0];
                    if (!best || best.score < 8) return null;
                    const rect = best.rect;
                    return {
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + (rect.height >= 60 ? rect.height * 0.74 : rect.height / 2)),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        tag: best.tag,
                        text: best.text.slice(0, 60),
                        strategy: 'dom_probe',
                    };
                }"""
            )
        except Exception:
            return None
        if not isinstance(target, dict):
            return None
        return target

    def _snapshot_to_blocking_error(self, snapshot: PageStateSnapshot, page_name: str) -> BlockingStateError:
        missing_anchor_note = ""
        if snapshot.missing_readiness_anchors:
            missing_anchor_note = f" 缺失锚点: {', '.join(snapshot.missing_readiness_anchors)}。"
        if snapshot.state == "captcha_blocked":
            return BlockingStateError(
                reason=BlockReason.CAPTCHA_BLOCKED,
                message=snapshot.reason or "Douyin captcha blocked the current session",
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action="Please complete the captcha / slider verification in this browser session.",
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state in {"unauthenticated", "login_modal"}:
            reason = BlockReason.LOGIN_REQUIRED
            if snapshot.detected_phrase and snapshot.detected_phrase in selectors.QR_LOGIN_HINTS:
                reason = BlockReason.QR_LOGIN_REQUIRED
            elif snapshot.detected_phrase and snapshot.detected_phrase in selectors.SMS_LOGIN_HINTS:
                reason = BlockReason.SMS_LOGIN_REQUIRED
            return BlockingStateError(
                reason=reason,
                message=snapshot.reason or "Douyin login is required before discovery can continue",
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action="Please log into Douyin in this persisted browser session.",
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state == "jingxuan_blocked_by_external_app_prompt":
            return BlockingStateError(
                reason=BlockReason.EXTERNAL_APP_INTERRUPTION,
                message=(snapshot.reason or "jingxuan recommend entry is blocked by a browser-native external-app prompt") + missing_anchor_note,
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action=(
                    "Please cancel the browser-native open-app / xdg-open prompt, uncheck 'Always allow' if it is checked, keep the page on /jingxuan, then press Enter to retry entering 推荐."
                ),
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state in {"public_jingxuan_landing", "jingxuan_ready_to_enter_recommend"}:
            return BlockingStateError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message=(snapshot.reason or "Douyin is still on the jingxuan landing page") + missing_anchor_note,
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action=(
                    "Keep the page on /jingxuan. The workflow will retry entering the 推荐 feed after you press Enter."
                ),
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state == "recommend_feed_shell":
            return BlockingStateError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message=(snapshot.reason or "Douyin recommend feed shell is visible but not yet interactable") + missing_anchor_note,
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action=(
                    "Please keep the current recommend video visible, dismiss overlays if any, wait for the feed card to stabilize, then press Enter to retry."
                ),
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state in {"creator_homepage_open", "self_profile_open"}:
            return BlockingStateError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message=snapshot.reason or "Douyin is still on a homepage/profile view",
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action="Please keep the page open. The workflow will retry returning to the recommend feed view after you press Enter.",
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state == "live_room_open":
            return BlockingStateError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message=snapshot.reason or "Douyin entered a live room and needs to return to the recommend feed",
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action="Please exit the live room and return to the recommend feed, or wait for the workflow to retry automatic live-room recovery.",
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state in {"public_feed", "visual_feed_unstable"}:
            action = (
                "Please scroll to a stable active card, dismiss overlays, wait for feed hydration, and retry on the current page."
                if snapshot.state == "visual_feed_unstable"
                else "Please navigate to stable Douyin web feed content and wait until the active card exposes creator/video/metric anchors."
            )
            return BlockingStateError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message=(snapshot.reason or "Douyin feed is not yet extractable") + missing_anchor_note,
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action=action,
                needs_user_action=True,
                resumable=True,
            )
        if snapshot.state == "abnormal/footer/download_page":
            reason = snapshot.blocking_reason or BlockReason.PAGE_STRUCTURE_UNCERTAINTY
            return BlockingStateError(
                reason=reason,
                message=(snapshot.reason or "Douyin is on an abnormal / download / open-app page") + missing_anchor_note,
                page_name=page_name,
                page_state=snapshot.state,
                screenshot_path=snapshot.screenshot_path,
                required_user_action=(
                    "Please dismiss any open-app / download-app / xdg-open interruption and return the page to normal Douyin web content."
                ),
                needs_user_action=True,
                resumable=True,
            )
        return BlockingStateError(
            reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            message=(snapshot.reason or "Douyin page state is not safe for extraction") + missing_anchor_note,
            page_name=page_name,
            page_state=snapshot.state,
            screenshot_path=snapshot.screenshot_path,
            required_user_action="Please provide a fresh screenshot or DOM snapshot of the current Douyin page.",
            needs_user_action=True,
            resumable=True,
        )

    def ensure_normal_feed(self, bootstrap_login: bool = False) -> PageStateSnapshot:
        attempt = 0
        while attempt < 6:
            attempt += 1
            snapshot = self.classify_page_state(debug_label=f"feed_gate_{attempt}", capture=True)
            self.logger.info(
                "douyin page-state gate",
                extra={
                    "attempt": attempt,
                    "raw_url": snapshot.page_url,
                    "page_state": snapshot.state,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "reason": snapshot.reason,
                    "detected_phrase": snapshot.detected_phrase,
                    "missing_readiness_anchors": snapshot.missing_readiness_anchors,
                    "screenshot_path": snapshot.screenshot_path,
                },
            )
            if snapshot.state in {"recommend_feed_shell", "recommended_feed_ready", "recommend_feed_interactable"}:
                self.logger.info(
                    "recommend feed interactable",
                    extra={
                        "page_url": snapshot.page_url,
                        "page_title": snapshot.page_title,
                        "page_state": snapshot.state,
                        "missing_readiness_anchors": snapshot.missing_readiness_anchors,
                    },
                )
                return snapshot
            if snapshot.state in {"public_jingxuan_landing", "jingxuan_ready_to_enter_recommend"}:
                self.logger.info(
                    "jingxuan landing detected",
                    extra={
                        "page_state": snapshot.state,
                        "page_url": snapshot.page_url,
                        "page_title": snapshot.page_title,
                    },
                )
                if self.enter_recommend_feed_from_jingxuan():
                    continue
                refreshed = self.classify_page_state(debug_label=f"jingxuan_recheck_{attempt}", capture=True)
                if refreshed.state != snapshot.state:
                    continue
                raise self._snapshot_to_blocking_error(refreshed, page_name="douyin_bootstrap")
            if snapshot.state == "recommend_feed_shell":
                self.logger.info(
                    "recommend feed shell reached",
                    extra={
                        "page_url": snapshot.page_url,
                        "page_title": snapshot.page_title,
                        "missing_readiness_anchors": snapshot.missing_readiness_anchors,
                    },
                )
                if self._attempt_ready_state_repair(snapshot, bootstrap_login=bootstrap_login):
                    continue
                raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_bootstrap")
            if snapshot.state == "creator_homepage_open":
                if self.close_creator_homepage_with_f(debug_label=f"feed_gate_return_{attempt}"):
                    continue
                raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_bootstrap")
            if snapshot.state == "live_room_open":
                self.logger.info(
                    "live room detected during feed gating; attempting automatic recovery",
                    extra={
                        "page_url": snapshot.page_url,
                        "page_title": snapshot.page_title,
                        "detected_phrase": snapshot.detected_phrase,
                    },
                )
                if self._recover_from_live_room(snapshot):
                    continue
                raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_bootstrap")
            if snapshot.state == "jingxuan_blocked_by_external_app_prompt":
                raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_bootstrap")
            if snapshot.state == "abnormal/footer/download_page" and self._recover_from_blocking_ui(snapshot):
                continue
            if self._attempt_ready_state_repair(snapshot, bootstrap_login=bootstrap_login):
                continue
            raise self._snapshot_to_blocking_error(snapshot, page_name="douyin_bootstrap")
        final_snapshot = self.classify_page_state(debug_label="feed_gate_exhausted", capture=True)
        raise self._snapshot_to_blocking_error(final_snapshot, page_name="douyin_bootstrap")

    def maybe_resolve_blocking_state(self, exc: BlockingStateError) -> bool:
        if exc.reason not in self.RESUMABLE_BLOCK_REASONS:
            return False
        try:
            snapshot = self.ensure_normal_feed(bootstrap_login=False)
            self.logger.info(
                "douyin blocking state resolved",
                extra={
                    "reason": exc.reason.value,
                    "resolved_page_state": snapshot.state,
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                },
            )
            return snapshot.state in {"recommended_feed_ready", "recommend_feed_interactable"}
        except BlockingStateError:
            return False
        except PageStructureUncertainError:
            return False

    def maybe_recover_from_target_closed(self, exc: Exception, context: str) -> bool:
        if not _is_target_closed_error(exc):
            return False
        self.logger.warning(
            "douyin target/page closed during operation",
            extra={
                "context": context,
                "browser_will_remain_open": True,
            },
        )
        return self._ensure_page_open(goto_base=True, reason=f"target_closed:{context}")

    def _attempt_ready_state_repair(self, snapshot: PageStateSnapshot, bootstrap_login: bool) -> bool:
        if snapshot.state in {"unauthenticated", "login_modal", "captcha_blocked"}:
            return False
        if snapshot.state in {"public_jingxuan_landing", "jingxuan_ready_to_enter_recommend"}:
            return self.enter_recommend_feed_from_jingxuan()
        if snapshot.state == "recommend_feed_shell":
            self.logger.info(
                "recommend feed shell repair attempting next-video action",
                extra={
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "missing_readiness_anchors": snapshot.missing_readiness_anchors,
                },
            )
            if self._click_next_feed_arrow(debug_label="recommend_feed_shell", reason="feed_shell_repair"):
                return True
            self.page.keyboard.press("PageDown")
            return self._wait_for_timeout_safe(1_000, reason="recommend_feed_shell_retry")
        if snapshot.state == "creator_homepage_open":
            return bool(self.close_creator_homepage_with_f(debug_label="return_from_creator_homepage"))
        if snapshot.state == "self_profile_open":
            return self._recover_from_self_profile(debug_label="ready_state_repair")
        if snapshot.state == "live_room_open":
            self.logger.info(
                "live room detected; attempting automatic recovery",
                extra={
                    "page_url": snapshot.page_url,
                    "page_title": snapshot.page_title,
                    "detected_phrase": snapshot.detected_phrase,
                },
            )
            return self._recover_from_live_room(snapshot)
        if snapshot.state == "jingxuan_blocked_by_external_app_prompt":
            self.logger.info(
                "blocked by external app prompt",
                extra={
                    "page_url": snapshot.page_url,
                    "page_state": snapshot.state,
                    "bootstrap_login": bootstrap_login,
                },
            )
            return False
        if snapshot.state == "abnormal/footer/download_page":
            self.logger.info(
                "douyin abnormal/download page requires manual confirmation after automatic blocking-ui recovery",
                extra={
                    "raw_url": snapshot.page_url,
                    "detected_phrase": snapshot.detected_phrase,
                    "bootstrap_login": bootstrap_login,
                },
            )
            return False
        if snapshot.state in {"public_feed", "visual_feed_unstable"}:
            return self._repair_feed_surface_state(snapshot)
        return False

    def _repair_feed_surface_state(self, snapshot: PageStateSnapshot) -> bool:
        self.logger.info(
            "repairing douyin feed surface before pausing",
            extra={
                "page_state": snapshot.state,
                "page_url": snapshot.page_url,
                "page_title": snapshot.page_title,
                "missing_readiness_anchors": snapshot.missing_readiness_anchors,
            },
        )
        if self._enter_recommendation_feed():
            if not self._wait_for_timeout_safe(1_200, reason=f"ready_state_repair:{snapshot.state}"):
                return False
            return True

        action_attempted = False
        repair_actions = (
            ("next_button", lambda: self._click_next_feed_arrow(debug_label="public_feed_repair", reason="public_feed_repair")),
            ("wheel_900", lambda: self._wheel_feed_surface(900, reason="public_feed_repair_wheel_900")),
            ("wheel_1500", lambda: self._wheel_feed_surface(1500, reason="public_feed_repair_wheel_1500")),
            ("pagedown", lambda: self._pagedown_feed_surface(reason="public_feed_repair_pagedown")),
            ("direct_recommend", self._goto_recommend_route_for_repair),
        )
        for action_name, action in repair_actions:
            try:
                repaired = action()
            except Exception as exc:
                self.logger.info(
                    "douyin feed surface repair action failed",
                    extra={
                        "action": action_name,
                        "page_url": self.page.url if self.page and not self.page.is_closed() else None,
                        "error_text": str(exc),
                    },
                )
                continue
            if not repaired:
                continue
            action_attempted = True
            refreshed = self.classify_page_state(debug_label=f"feed_surface_repair_{action_name}", capture=False)
            if refreshed.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                return True
            if refreshed.state not in {"public_feed", "visual_feed_unstable"}:
                return True
        return action_attempted

    def _wheel_feed_surface(self, distance: int, reason: str) -> bool:
        self.logger.info(
            "repairing feed surface with mouse wheel",
            extra={"distance": distance, "page_url": self.page.url, "page_title": self._safe_title()},
        )
        self.page.mouse.wheel(0, distance)
        return self._wait_for_timeout_safe(1_000, reason=reason)

    def _pagedown_feed_surface(self, reason: str) -> bool:
        self.logger.info(
            "repairing feed surface with PageDown",
            extra={"page_url": self.page.url, "page_title": self._safe_title()},
        )
        self.page.keyboard.press("PageDown")
        return self._wait_for_timeout_safe(1_100, reason=reason)

    def _goto_recommend_route_for_repair(self) -> bool:
        self.logger.info(
            "repairing feed surface by navigating directly to recommend route",
            extra={"page_url": self.page.url, "page_title": self._safe_title()},
        )
        self.page.goto("https://www.douyin.com/?recommend=1&from_nav=1", wait_until="domcontentloaded", timeout=25_000)
        return self._wait_for_timeout_safe(1_200, reason="public_feed_repair_direct_recommend")

    def _recover_from_self_profile(self, debug_label: str | None = None) -> bool:
        self.logger.info(
            "recovering from self profile back to recommend feed",
            extra={
                "page_url": self.page.url if self.page and not self.page.is_closed() else None,
                "page_title": self._safe_title(),
                "debug_label": debug_label,
            },
        )
        try:
            if self.page and not self.page.is_closed():
                self.page.go_back(wait_until="domcontentloaded", timeout=10_000)
                if self._wait_for_timeout_safe(900, reason="self_profile_go_back"):
                    snapshot = self.classify_page_state(
                        debug_label=f"{debug_label}_self_profile_go_back" if debug_label else "self_profile_go_back",
                        capture=False,
                    )
                    if snapshot.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                        return True
        except Exception:
            pass
        try:
            if self._goto_recommend_route_for_repair():
                snapshot = self.classify_page_state(
                    debug_label=f"{debug_label}_self_profile_direct_recommend" if debug_label else "self_profile_direct_recommend",
                    capture=False,
                )
                return snapshot.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready", "public_feed", "visual_feed_unstable"}
        except Exception:
            return False
        return False

    def _enter_recommendation_feed(self) -> bool:
        if not self._ensure_page_open(goto_base=False, reason="enter_recommendation_feed"):
            return False
        if "/jingxuan" in ((self.page.url or "").lower()):
            return self.enter_recommend_feed_from_jingxuan()
        if self._extract_active_feed_state() is not None:
            return True
        for selector in selectors.FEED_ENTRY_SELECTORS:
            locator = first_visible_locator(self.page, [selector], timeout_ms=600)
            if locator is None:
                continue
            try:
                locator.click(timeout=900)
                if not self._wait_for_timeout_safe(900, reason=f"feed_entry_click:{selector}"):
                    return False
                if self._extract_active_feed_state() is not None:
                    return True
                post_click_state = self.classify_page_state(debug_label="feed_entry_click_post", capture=False)
                if post_click_state.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                    return True
            except Exception as exc:
                if _is_target_closed_error(exc):
                    self.logger.warning(
                        "douyin page closed during feed entry click",
                        extra={
                            "selector": selector,
                            "browser_will_remain_open": True,
                        },
                    )
                    self._ensure_page_open(goto_base=True, reason="feed_entry_click_closed")
                    return False
                continue
        try:
            self.logger.info(
                "feed entry selectors did not stabilize; navigating directly to recommend route",
                extra={
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )
            self.page.goto("https://www.douyin.com/?recommend=1&from_nav=1", wait_until="domcontentloaded", timeout=25_000)
            if not self._wait_for_timeout_safe(1_100, reason="enter_recommendation_feed_direct_goto"):
                return False
            snapshot = self.classify_page_state(debug_label="post_direct_recommend_goto", capture=False)
            return snapshot.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}
        except Exception:
            return self._extract_active_feed_state() is not None
        
    def enter_recommend_feed_from_jingxuan(self) -> bool:
        """
        进入 Douyin 推荐流，不依赖首页 URL 是 /jingxuan。
        如果当前页无法直接点击推荐，直接跳转到 ?recommend=1
        """
        # 确保页面打开
        if not self._ensure_page_open(goto_base=False, reason="enter_recommend_feed_from_jingxuan"):
            return False

        direct_recommend_url = "https://www.douyin.com/?recommend=1&from_nav=1"

        # 关键函数：直接跳推荐流
        def _goto_direct_recommend(reason: str) -> bool:
            self.logger.info(
                "跳转到直接推荐流",
                extra={
                    "reason": reason,
                    "page_url": getattr(self.page, "url", None),
                    "page_title": self._safe_title(),
                    "direct_recommend_url": direct_recommend_url,
                },
            )
            try:
                self.page.goto(
                    direct_recommend_url,
                    wait_until="domcontentloaded",
                    timeout=25_000,
                )
                self.page.wait_for_timeout(2_500)
            except Exception as exc:
                self.logger.warning(
                    "直接推荐流跳转失败",
                    extra={
                        "reason": reason,
                        "error": str(exc),
                        "page_url": getattr(self.page, "url", None),
                        "page_title": self._safe_title(),
                    },
                )
                return False

            # 尝试清理可能存在的弹窗或浮层
            for key in ("Escape", "Escape", "ArrowDown"):
                try:
                    self.page.keyboard.press(key)
                    self.page.wait_for_timeout(500)
                except Exception:
                    pass
            try:
                self.page.mouse.wheel(0, 1000)
                self.page.wait_for_timeout(800)
            except Exception:
                pass

            return True

        # 1️⃣ 如果当前页有“推荐”按钮，尝试点击
        locator = self._find_jingxuan_recommend_target(timeout_ms=800)
        if locator:
            try:
                locator.scroll_into_view_if_needed(timeout=1_000)
                locator.click(timeout=1_200)
                self._wait_for_timeout_safe(1_500, reason="jingxuan_recommend_click")
                self.logger.info(
                    "点击 jingxuan 推荐成功"
                )
                return True
            except Exception:
                # 点击失败直接跳推荐流
                return _goto_direct_recommend("recommend_click_failed")
        else:
            # 找不到按钮直接跳推荐流
            return _goto_direct_recommend("recommend_target_not_visible")

    def _find_jingxuan_recommend_target(self, timeout_ms: int = 600):
        return first_visible_locator(self.page, selectors.JINGXUAN_RECOMMEND_SELECTORS, timeout_ms=timeout_ms)

    def _extract_recommend_href(self, locator) -> str | None:
        href: str | None = None
        try:
            href = locator.evaluate(
                """(node) => {
                    const anchor =
                        (node instanceof Element && node.matches('a[href]') ? node : null) ||
                        (node instanceof Element ? node.closest('a[href]') : null) ||
                        (node instanceof Element ? node.querySelector('a[href]') : null);
                    if (!anchor) {
                        return null;
                    }
                    return anchor.href || anchor.getAttribute('href');
                }"""
            )
        except Exception:
            href = None
        if not href:
            try:
                href = locator.get_attribute("href", timeout=600)
            except Exception:
                href = None
        if not href:
            return None
        normalized = urljoin(selectors.BASE_URL, href.strip())
        return normalized or None

    @staticmethod
    def _looks_like_recommend_href(href: str | None) -> bool:
        if not href:
            return False
        parsed = urlparse(href)
        if "douyin.com" not in (parsed.netloc or "").lower():
            return False
        query = parse_qs(parsed.query)
        recommend_value = "".join(query.get("recommend", []))
        from_nav_value = "".join(query.get("from_nav", []))
        return recommend_value == "1" or from_nav_value == "1"

    def _mark_jingxuan_recommend_blocked(self, reason: str) -> None:
        self._jingxuan_recommend_blocked = True
        self._jingxuan_recommend_block_reason = reason

    def _clear_jingxuan_recommend_block(self) -> None:
        self._jingxuan_recommend_blocked = False
        self._jingxuan_recommend_block_reason = None

    def _wait_for_timeout_safe(self, timeout_ms: int, reason: str) -> bool:
        if not self._ensure_page_open(goto_base=False, reason=reason):
            return False
        try:
            self.page.wait_for_timeout(timeout_ms)
            return True
        except Exception as exc:
            if _is_target_closed_error(exc):
                self.logger.warning(
                    "douyin page closed during wait; reopening page",
                    extra={
                        "reason": reason,
                        "timeout_ms": timeout_ms,
                        "browser_will_remain_open": True,
                    },
                )
                return self._ensure_page_open(goto_base=True, reason=f"reopen_after_wait:{reason}")
            raise
    
    def _ensure_page_open(self, goto_base: bool, reason: str) -> bool:
        if self.page is not None:
            try:
                if not self.page.is_closed():
                    return True
            except Exception:
                pass
        context = None
        if self.page is not None:
            try:
                context = self.page.context
            except Exception:
                context = None
        if context is None:
            self.logger.warning(
                "douyin page is unavailable and no browser context can be recovered",
                extra={
                    "reason": reason,
                    "browser_will_remain_open": False,
                },
            )
            return False
        try:
            live_pages = [page for page in context.pages if not page.is_closed()]
            self.page = live_pages[0] if live_pages else context.new_page()
            self.page.on("dialog", lambda dialog: dialog.dismiss())
            self._response_listener_registered = False
            self._register_response_listener()
            self.logger.warning(
                "douyin page unexpectedly closed; reopened page in persistent context",
                extra={
                    "reason": reason,
                    "browser_will_remain_open": True,
                    "goto_base": goto_base,
                },
            )
            if goto_base:
                self.page.goto(selectors.BASE_URL, wait_until="domcontentloaded", timeout=25_000)
                try:
                    self.page.wait_for_timeout(800)
                except Exception as exc:
                    if _is_target_closed_error(exc):
                        self.logger.warning(
                            "douyin reopened page closed again during root stabilization",
                            extra={
                                "reason": reason,
                                "browser_will_remain_open": True,
                            },
                        )
                        return False
                    raise
            return True
        except Exception as exc:
            self.logger.warning(
                "douyin failed to reopen page in persistent context: %s",
                exc,
            )
            return False

    @staticmethod
    def _is_recommend_route(url: str | None) -> bool:
        lowered = (url or "").lower()
        return any(token in lowered for token in ("recommend=1", "/?recommend", "&from_nav=1"))

    @staticmethod
    def _looks_like_self_profile(url: str | None) -> bool:
        lowered = (url or "").lower()
        return "/user/self" in lowered or "sec_user_id=self" in lowered

    @staticmethod
    def _feed_is_interactable(active_feed: dict | None) -> bool:
        if active_feed is None:
            return False
        active_text = (active_feed.get("active_text") or "").strip()
        interaction_x = active_feed.get("interaction_x")
        interaction_y = active_feed.get("interaction_y")
        return bool(active_text and len(active_text) >= 12 and interaction_x is not None and interaction_y is not None)

    def _minimal_feed_shell_ready(self, active_feed: dict | None, page_text: str | None) -> bool:
        if self._feed_is_interactable(active_feed):
            return True
        if not self._is_recommend_route(self.page.url):
            return False
        if first_visible_locator(self.page, selectors.NEXT_VIDEO_BUTTON_SELECTORS, timeout_ms=250) is None:
            return False
        page_body = page_text or body_text(self.page, timeout_ms=500)
        if page_body and _contains_any(page_body, selectors.FEED_TEXT_HINTS):
            return True
        try:
            return bool(
                self.page.evaluate(
                    """() => {
                        const media = document.querySelectorAll('video, img, canvas');
                        return [...media].some((el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 200 && rect.height > 200 && rect.top < window.innerHeight * 0.9 && rect.bottom > window.innerHeight * 0.1;
                        });
                    }"""
                )
            )
        except Exception:
            return False

    def _looks_like_feed_surface(self, text: str | None, active_feed: dict | None) -> bool:
        if active_feed is not None:
            return True
        lowered_url = (self.page.url or "").lower()
        if any(token in lowered_url for token in ("/jingxuan", "/recommend", "/?recommend", "douyin.com")) and _contains_any(text, selectors.FEED_TEXT_HINTS):
            return True
        return sum(1 for hint in selectors.FEED_TEXT_HINTS if hint in (text or "")) >= 2

    def _inspect_feed_readiness(self, active_feed: dict | None, page_text: str | None) -> tuple[list[str], dict[str, str | None]]:
        details: dict[str, str | None] = {
            "creator_name": None,
            "creator_profile_url": None,
            "video_url": None,
            "metric_anchor": None,
            "active_text": _summarize_text((active_feed or {}).get("active_text") if active_feed else page_text, limit=120),
        }
        missing: list[str] = []
        if active_feed is None:
            return ["active_feed_item", "creator_name", "creator_anchor", "video_anchor", "interaction_metric"], details

        card = first_visible_locator(self.page, selectors.ACTIVE_CARD_SELECTORS, timeout_ms=300)
        raw_text = (active_feed.get("active_text") if active_feed else None) or (locator_text(card) if card is not None else None) or page_text or ""
        creator_name = (
            _sanitize_creator_name(active_feed.get("creator_name") if active_feed else None)
            or _sanitize_creator_name(first_text(card, selectors.CREATOR_NAME_SELECTORS) if card is not None else None)
            or _extract_creator_name(raw_text)
        )
        creator_profile_url = (active_feed.get("creator_profile_url") if active_feed else None) or (first_attribute(card, selectors.CREATOR_LINK_SELECTORS, "href") if card is not None else None)
        video_url = (active_feed.get("video_url") if active_feed else None) or (first_attribute(card, selectors.VIDEO_LINK_SELECTORS, "href") if card is not None else None)
        like_count_raw = (first_text(card, selectors.LIKE_COUNT_SELECTORS) if card is not None else None) or _extract_metric(raw_text, "点赞")
        comment_count_raw = (first_text(card, selectors.COMMENT_COUNT_SELECTORS) if card is not None else None) or _extract_metric(raw_text, "评论")
        favorite_count_raw = (first_text(card, selectors.FAVORITE_COUNT_SELECTORS) if card is not None else None) or _extract_metric(raw_text, "收藏")
        share_count_raw = (first_text(card, selectors.SHARE_COUNT_SELECTORS) if card is not None else None) or _extract_metric(raw_text, "分享")

        creator_profile_url = _normalize_url(creator_profile_url)
        if self._looks_like_self_profile(creator_profile_url):
            creator_profile_url = None
        video_url = _normalize_url(video_url)

        details.update(
            {
                "creator_name": creator_name,
                "creator_profile_url": creator_profile_url,
                "video_url": video_url,
                "metric_anchor": like_count_raw or comment_count_raw or favorite_count_raw or share_count_raw,
            }
        )
        if not raw_text.strip():
            missing.append("active_feed_item")
        if not creator_name:
            missing.append("creator_name")
        if not creator_profile_url or "/user/" not in creator_profile_url:
            missing.append("creator_anchor")
        if not video_url or "/video/" not in video_url:
            missing.append("video_anchor")
        if not any((like_count_raw, comment_count_raw, favorite_count_raw, share_count_raw)):
            missing.append("interaction_metric")
        return missing, details

    @staticmethod
    def _build_readiness_reason(missing_anchors: list[str], details: dict[str, str | None]) -> str:
        if not missing_anchors:
            return "readiness anchors complete"
        detail_parts = [
            f"creator_name={details.get('creator_name')}" if details.get("creator_name") else None,
            f"creator_profile_url={details.get('creator_profile_url')}" if details.get("creator_profile_url") else None,
            f"video_url={details.get('video_url')}" if details.get("video_url") else None,
            f"metric_anchor={details.get('metric_anchor')}" if details.get("metric_anchor") else None,
        ]
        detail_text = " | ".join(part for part in detail_parts if part)
        if detail_text:
            return f"missing anchors: {', '.join(missing_anchors)}; observed: {detail_text}"
        return f"missing anchors: {', '.join(missing_anchors)}"

    def _collect_video_cards(self, limit: int) -> list[ProfileVideoCard]:
        cards: list[ProfileVideoCard] = []

        # 1. 先尝试点击右侧面板的 “TA的作品” tab
        try:
            for selector in getattr(selectors, "PROFILE_WORKS_TAB_SELECTORS", []):
                try:
                    tab = self.page.locator(selector).first
                    if tab.count() > 0 and tab.is_visible(timeout=500):
                        tab.click(timeout=1000)

                        # 等 TA 的作品区域加载，900ms 有时太短
                        self.page.wait_for_timeout(1800)

                        # 多次轻微滚动右侧作品区域，触发懒加载
                        for scroll_index in range(3):
                            try:
                                self.page.mouse.wheel(0, 500)
                                self.page.wait_for_timeout(700)
                            except Exception:
                                pass

                        self.logger.info(
                            "profile works tab clicked",
                            extra={
                                "selector": selector,
                                "page_url": self.page.url,
                                "page_title": self._safe_title(),
                            },
                        )
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # 2. 原来的 selector 方式，保留
        for selector in selectors.PROFILE_VIDEO_CARD_SELECTORS:
            try:
                locator = self.page.locator(selector)
                count = locator.count()

                self.logger.info(
                    "profile video card selector probe",
                    extra={
                        "selector": selector,
                        "count": count,
                    },
                )

                if not count:
                    continue

                for index in range(min(count, limit)):
                    item = locator.nth(index)
                    text = locator_text(item) or ""

                    href = (
                        item.get_attribute("href")
                        or first_attribute(item, selectors.VIDEO_LINK_SELECTORS, "href")
                    )
                    href = _normalize_url(href)

                    like_raw = (
                        first_text(item, selectors.PROFILE_VIDEO_LIKE_SELECTORS)
                        or _extract_profile_card_like_from_text(text)
                        or _extract_metric(text, "点赞")
                    )

                    title = (
                        first_text(item, selectors.PROFILE_VIDEO_TITLE_SELECTORS)
                        or _extract_profile_card_title_from_text(text)
                        or (text.splitlines()[0].strip() if text else None)
                    )

                    cards.append(
                        ProfileVideoCard(
                            url=href,
                            title=title,
                            like_raw=like_raw,
                            is_pinned="置顶" in text,
                        )
                    )

                if cards:
                    return cards[:limit]

            except Exception as exc:
                self.logger.info(
                    "profile video card selector failed",
                    extra={
                        "selector": selector,
                        "error": str(exc),
                    },
                )
                continue

        # 3. 如果 selector 全部失败，使用 DOM fallback 扫描右侧面板
        fallback_items = []
        try:
            fallback_items = self.page.evaluate(
                """
                (limit) => {
                    const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();

                    const likePattern = /^\\d+(?:\\.\\d+)?(?:万|亿|w|W|k|K)?$/;

                    function visible(el) {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (!style) return false;
                        if (style.display === "none" || style.visibility === "hidden") return false;
                        if (Number(style.opacity || "1") === 0) return false;

                        const r = el.getBoundingClientRect();
                        return r.width > 20 && r.height > 20 && r.right > 0 && r.bottom > 0;
                    }

                    function rectObj(el) {
                        const r = el.getBoundingClientRect();
                        return {
                            left: Math.round(r.left),
                            top: Math.round(r.top),
                            width: Math.round(r.width),
                            height: Math.round(r.height),
                        };
                    }

                    function textOf(el) {
                        return clean([
                            el.innerText || "",
                            el.textContent || "",
                            el.getAttribute("aria-label") || "",
                            el.getAttribute("title") || "",
                        ].join(" "));
                    }

                    const vw = window.innerWidth || document.documentElement.clientWidth || 0;

                    // 优先找右侧包含 “TA的作品” 的面板
                    const containers = Array.from(document.querySelectorAll("div, section, aside, main"))
                        .filter((el) => {
                            if (!visible(el)) return false;
                            const r = el.getBoundingClientRect();
                            const text = textOf(el);

                            if (r.left < vw * 0.45) return false;
                            if (r.width < 180 || r.height < 160) return false;

                            return text.includes("TA的作品") || text.includes("详情");
                        })
                        .sort((a, b) => {
                            const ar = a.getBoundingClientRect();
                            const br = b.getBoundingClientRect();
                            return (br.width * br.height) - (ar.width * ar.height);
                        });

                    const root = containers[0] || document.body;

                    const nodes = Array.from(root.querySelectorAll("a, div, li, article"))
                        .filter((el) => {
                            if (!visible(el)) return false;

                            const r = el.getBoundingClientRect();
                            const text = textOf(el);

                            if (r.left < vw * 0.45) return false;
                            if (r.width < 70 || r.height < 45) return false;
                            if (!text) return false;

                            // 排除 tab、评论、相关推荐等明显不是作品卡片的区域
                            if (/^(详情|TA的作品|评论|问AI|相关推荐|大家都在搜)/.test(text)) return false;
                            if (text.includes("全部评论")) return false;
                            if (text.includes("分享") && text.includes("回复")) return false;

                            // 作品卡片一般会有数字点赞量
                            return /\\d+(?:\\.\\d+)?(?:万|亿|w|W|k|K)?/.test(text);
                        })
                        .map((el) => {
                            const text = textOf(el);
                            const lines = text
                                .split(/\\n|\\s{2,}/)
                                .map(clean)
                                .filter(Boolean);

                            let href = null;
                            if (el.matches && el.matches("a[href]")) {
                                href = el.href || el.getAttribute("href");
                            } else {
                                const a = el.querySelector && el.querySelector("a[href]");
                                if (a) href = a.href || a.getAttribute("href");
                            }

                            // 从所有短数字里找最像点赞量的一个
                            const candidates = lines
                                .flatMap((line) => line.split(/\\s+/).map(clean))
                                .filter((part) => likePattern.test(part));

                            const likeRaw = candidates.length ? candidates[candidates.length - 1] : null;

                            const titleLine = lines.find((line) => {
                                if (!line) return false;
                                if (likePattern.test(line)) return false;
                                if (line.includes("置顶")) return false;
                                if (line.length > 80) return false;
                                return true;
                            }) || null;

                            return {
                                href,
                                title: titleLine,
                                like_raw: likeRaw,
                                is_pinned: text.includes("置顶"),
                                rect: rectObj(el),
                                text_preview: text.slice(0, 120),
                            };
                        })
                        .filter((item) => item.like_raw || item.title || item.href);

                    // 简单去重：按位置 + 文本
                    const seen = new Set();
                    const results = [];

                    for (const item of nodes) {
                        const key = [
                            item.href || "",
                            item.like_raw || "",
                            item.title || "",
                            item.rect.left,
                            item.rect.top,
                        ].join("|");

                        if (seen.has(key)) continue;
                        seen.add(key);

                        results.push(item);
                        if (results.length >= limit) break;
                    }

                    return results;
                }
                """,
                limit,
            )
        except Exception as exc:
            self.logger.info(
                "profile video card dom fallback failed",
                extra={"error": str(exc)},
            )
            fallback_items = []

        for item in fallback_items or []:
            cards.append(
                ProfileVideoCard(
                    url=_normalize_url((item or {}).get("href")),
                    title=(item or {}).get("title"),
                    like_raw=(item or {}).get("like_raw"),
                    is_pinned=bool((item or {}).get("is_pinned")),
                )
            )

        self.logger.info(
            "profile video card dom fallback result",
            extra={
                "fallback_count": len(cards),
                "fallback_like_raws": [card.like_raw for card in cards],
                "fallback_titles": [card.title for card in cards],
            },
        )

        return cards[:limit]
    
    def _extract_profile_card_like_from_text(text: str | None) -> str | None:
        if not text:
            return None

        parts = [
            part.strip()
            for part in re.split(r"[\s\n\r\t]+", text)
            if part and part.strip()
        ]

        number_like_parts = [
            part
            for part in parts
            if re.fullmatch(r"\d+(?:\.\d+)?(?:万|亿|w|W|k|K)?", part)
        ]

        if not number_like_parts:
            return None

        return number_like_parts[-1]


    def _extract_profile_card_title_from_text(text: str | None) -> str | None:
        if not text:
            return None

        lines = [
            line.strip()
            for line in re.split(r"[\n\r]+", text)
            if line and line.strip()
        ]

        for line in lines:
            if "置顶" in line:
                continue
            if re.fullmatch(r"\d+(?:\.\d+)?(?:万|亿|w|W|k|K)?", line):
                continue
            if line in {"TA的作品", "详情", "评论", "问AI", "相关推荐"}:
                continue
            if len(line) <= 80:
                return line

        return None

    def _looks_like_profile(self) -> bool:
        if "/user/" in (self.page.url or ""):
            return True
        profile_ready = first_visible_locator(self.page, selectors.PROFILE_READY_SELECTORS[:2], timeout_ms=800)
        if profile_ready is not None:
            return True
        text = body_text(self.page, timeout_ms=800)
        return ("粉丝" in text and "获赞" in text) or ("粉丝" in text and "IP属地" in text)

    def _detect_live_room_phrase(self, current_url: str | None, text: str | None, looks_like_feed: bool) -> str | None:
        lowered_url = (current_url or "").lower()
        if any(token in lowered_url for token in ("/live", "live.douyin.com", "/room")):
            return "url_live_room"
        haystack = text or ""
        hits = [hint for hint in selectors.LIVE_ROOM_HINTS if hint in haystack]
        if len(hits) >= 2 and not looks_like_feed:
            return " / ".join(hits[:3])
        return None

    def _wait_for_profile_entry(self, previous_url: str) -> bool:
        for _ in range(8):
            self.page.wait_for_timeout(450)
            self.raise_for_blockers(page_name="douyin_profile_entry")
            if self._looks_like_profile():
                return True
            if self.page.url != previous_url and "/user/" in self.page.url:
                return True
        return False

    def _wait_for_creator_homepage_state(
        self,
        opening: bool,
        previous_url: str,
        debug_label: str | None = None,
    ) -> PageStateSnapshot:
        for attempt in range(1, 11):
            if not self._wait_for_timeout_safe(450, reason=f"creator_homepage_toggle_{'open' if opening else 'close'}_{attempt}"):
                continue
            snapshot = self.classify_page_state(
                debug_label=f"{debug_label}_{'homepage_open' if opening else 'homepage_close'}_{attempt}" if debug_label else None,
                capture=False,
            )
            if snapshot.state in {
                "unauthenticated",
                "login_modal",
                "captcha_blocked",
                "jingxuan_blocked_by_external_app_prompt",
                "public_jingxuan_landing",
                "jingxuan_ready_to_enter_recommend",
                "abnormal/footer/download_page",
                "live_room_open",
                "self_profile_open",
            }:
                if snapshot.state == "live_room_open" and self._recover_from_live_room(snapshot):
                    continue
                if snapshot.state == "self_profile_open" and self._recover_from_self_profile(debug_label=debug_label):
                    continue
                raise self._snapshot_to_blocking_error(
                    snapshot,
                    page_name="douyin_creator_homepage_open" if opening else "douyin_creator_homepage_close",
                )
            if opening:
                if (
                    snapshot.state == "creator_homepage_open"
                    or (self._looks_like_profile() and not self._looks_like_self_profile(self.page.url))
                    or (
                        self.page.url != previous_url
                        and "/user/" in (self.page.url or "")
                        and not self._looks_like_self_profile(self.page.url)
                    )
                ):
                    self.logger.info(
                        "creator homepage detected",
                        extra={
                            "page_url": self.page.url,
                            "page_title": self._safe_title(),
                            "attempt": attempt,
                        },
                    )
                    return PageStateSnapshot(
                        state="creator_homepage_open",
                        page_url=self.page.url,
                        page_title=self._safe_title(),
                        visible_text_summary=snapshot.visible_text_summary,
                        reason="F 键后检测到达人主页态。",
                    )
            else:
                if snapshot.state in {"recommend_feed_shell", "recommend_feed_interactable", "recommended_feed_ready"}:
                    return snapshot
        if opening:
            if self._wait_for_timeout_safe(1_000, reason="creator_homepage_toggle_open_grace"):
                late_snapshot = self.classify_page_state(
                    debug_label=f"{debug_label}_homepage_open_grace" if debug_label else None,
                    capture=True,
                )
                if (
                    late_snapshot.state == "creator_homepage_open"
                    or (self._looks_like_profile() and not self._looks_like_self_profile(self.page.url))
                    or (
                        self.page.url != previous_url
                        and "/user/" in (self.page.url or "")
                        and not self._looks_like_self_profile(self.page.url)
                    )
                ):
                    self.logger.info(
                        "creator homepage detected after grace wait",
                        extra={
                            "page_url": self.page.url,
                            "page_title": self._safe_title(),
                        },
                    )
                    return PageStateSnapshot(
                        state="creator_homepage_open",
                        page_url=self.page.url,
                        page_title=self._safe_title(),
                        visible_text_summary=late_snapshot.visible_text_summary,
                        reason="F 键后主页切换较慢，grace wait 后检测到达人主页态。",
                    )
        if opening:
            screenshot = self._capture(
                f"douyin_creator_homepage_open_failed_{debug_label}" if debug_label else "douyin_creator_homepage_open_failed"
            )
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="已按下 F，但未能稳定检测到达人主页打开。",
                page_name="douyin_creator_homepage_open",
                screenshot_path=screenshot,
                required_user_action="Please provide the screenshot or DOM snapshot right after pressing F on the active Douyin feed item.",
                resumable=True,
            )
        screenshot = self._capture(
            f"douyin_creator_homepage_close_failed_{debug_label}" if debug_label else "douyin_creator_homepage_close_failed"
        )
        raise PageStructureUncertainError(
            reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            message="已再次按下 F，但未能确认返回推荐流。",
            page_name="douyin_creator_homepage_close",
            screenshot_path=screenshot,
            required_user_action="Please keep the page on the current Douyin view, then provide a screenshot or retry after the feed shell reappears.",
            resumable=True,
        )

    def _remember_aweme_payload(self, payload: dict | list) -> None:
        for item in _extract_aweme_items(payload):
            video_id = item.get("video_id")
            video_url = item.get("video_url")
            if not video_id or not video_url:
                continue
            entry = {
                "video_id": video_id,
                "video_url": video_url,
                "creator_name": item.get("creator_name"),
                "creator_profile_url": item.get("creator_profile_url"),
                "description": item.get("description"),
                "captured_at": time.monotonic(),
            }
            self._recent_aweme_items = [
                existing for existing in self._recent_aweme_items if existing.get("video_id") != video_id
            ]
            self._recent_aweme_items.append(entry)
        if len(self._recent_aweme_items) > 80:
            self._recent_aweme_items = self._recent_aweme_items[-80:]

    def _remember_comment_payload(self, payload: dict | list, response_url: str | None = None) -> None:
        fallback_video_id = _extract_video_id_from_response_url(response_url)
        pairs = _extract_comment_threads(payload, fallback_video_id=fallback_video_id)
        for video_id, comments in pairs:
            if not video_id or not comments:
                continue
            self._recent_comments_by_video_id[video_id] = comments[:8]
            self._recent_comment_meta_by_video_id[video_id] = {
                "request_url": response_url,
                "captured_at": time.monotonic(),
                "count": len(comments[:8]),
            }
        if len(self._recent_comments_by_video_id) > 80:
            retained_ids = list(self._recent_comments_by_video_id.keys())[-80:]
            self._recent_comments_by_video_id = {
                video_id: self._recent_comments_by_video_id[video_id]
                for video_id in retained_ids
            }
            self._recent_comment_meta_by_video_id = {
                video_id: self._recent_comment_meta_by_video_id.get(video_id, {})
                for video_id in retained_ids
            }

    def _clear_recent_comment_payload(self, video_id: str | None) -> None:
        if not video_id:
            return
        self._recent_comments_by_video_id.pop(video_id, None)
        self._recent_comment_meta_by_video_id.pop(video_id, None)

    def _get_recent_network_comments(self, video_id: str | None) -> tuple[list[CommentSnippet], str | None]:
        if not video_id:
            return [], None
        comments = self._recent_comments_by_video_id.get(video_id, [])[:5]
        meta = self._recent_comment_meta_by_video_id.get(video_id, {})
        request_url = meta.get("request_url") if isinstance(meta, dict) else None
        return comments, str(request_url) if request_url else None

    def _match_recent_aweme_item(self, candidate: FeedCandidateSnapshot) -> dict | None:
        candidate_video_id = _extract_video_id_from_url(candidate.video_url)
        if candidate_video_id:
            for item in reversed(self._recent_aweme_items):
                if item.get("video_id") == candidate_video_id:
                    return item
        candidate_creator_url = _normalize_url(candidate.creator_profile_url)
        candidate_creator_name = _sanitize_creator_name(candidate.creator_name)
        description = candidate.video_description_raw or _clean_video_description_text(candidate.raw_text)
        for item in reversed(self._recent_aweme_items):
            if candidate_creator_url and _normalize_url(item.get("creator_profile_url")) == candidate_creator_url:
                return item
            if candidate_creator_name and _sanitize_creator_name(item.get("creator_name")) == candidate_creator_name:
                return item
            network_description = _clean_video_description_text(item.get("description"))
            if description and network_description and _text_overlap_score(description, network_description) >= 0.4:
                return item
        return None

    def _focus_active_feed(self, state: dict) -> None:
        center_x = int(state.get("interaction_x") or 720)
        center_y = int(state.get("interaction_y") or 540)
        try:
            self.page.mouse.move(center_x, center_y)
        except Exception:
            pass

    def _focus_feed_shell(self) -> None:
        try:
            self.page.mouse.move(720, 540)
        except Exception:
            pass
        try:
            self.page.locator("body").click(position={"x": 720, "y": 540}, timeout=700)
        except Exception:
            try:
                self.page.locator("body").click(timeout=700)
            except Exception:
                pass
        try:
            self.page.evaluate(
                """() => {
                    if (document.body) {
                        document.body.tabIndex = -1;
                        document.body.focus();
                    }
                }"""
            )
        except Exception:
            pass
        try:
            self.page.evaluate(
                """() => {
                    if (document.body) {
                        document.body.tabIndex = -1;
                        document.body.focus();
                    }
                }"""
            )
        except Exception:
            pass

    def _extract_active_feed_state(self) -> dict | None:
        lower_url = (self.page.url or "").lower()
        if any(token in lower_url for token in ("/root/live/", "live.douyin.com", "/live/")):
            return None
        try:
            state = self.page.evaluate(
                """(hints, chromeHints, footerHints) => {
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (!style || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) {
                            return false;
                        }
                        const rect = el.getBoundingClientRect();
                        return rect.width > 80 && rect.height > 80 && rect.bottom > 0 && rect.right > 0 && rect.top < window.innerHeight && rect.left < window.innerWidth;
                    };
                    const cleanText = (value) => (value || '').replace(/\\s+/g, ' ').trim();
                    const centerX = window.innerWidth / 2;
                    const centerY = window.innerHeight / 2;
                    const containers = [];
                    const seen = new Set();
                    const countHits = (text, parts) => parts.filter((part) => text.includes(part)).length;
                    const pushContainer = (el, source) => {
                        if (!el || seen.has(el) || !isVisible(el)) return;
                        seen.add(el);
                        const rect = el.getBoundingClientRect();
                        const text = cleanText(el.innerText);
                        if (!text) return;
                        const hintHits = hints.filter((hint) => text.includes(hint)).length;
                        const chromeHits = countHits(text, chromeHints);
                        const footerHits = countHits(text, footerHints);
                        const containsCenter = rect.left <= centerX && rect.right >= centerX && rect.top <= centerY && rect.bottom >= centerY;
                        if (!containsCenter) return;
                        const mediaHits = el.querySelectorAll('video, img, canvas').length;
                        const anchorHits = el.querySelectorAll("a[href*='/video/'], a[href*='/user/']").length;
                        if (footerHits >= 1 && text.length > 160) return;
                        if (chromeHits >= 6 && anchorHits === 0 && mediaHits === 0) return;
                        const distance = Math.abs(rect.left + rect.width / 2 - centerX) + Math.abs(rect.top + rect.height / 2 - centerY);
                        const score =
                            hintHits * 8 +
                            Math.min((rect.width * rect.height) / 150000, 4) +
                            Math.min(mediaHits, 3) * 6 +
                            Math.min(anchorHits, 3) * 5 -
                            chromeHits * 1.5 -
                            footerHits * 8 -
                            distance / 320;
                        containers.push({
                            element: el,
                            text,
                            score,
                            hintHits,
                            chromeHits,
                            footerHits,
                            mediaHits,
                            anchorHits,
                            source,
                            rect: {
                                left: rect.left,
                                top: rect.top,
                                width: rect.width,
                                height: rect.height,
                            },
                        });
                    };
                    const centerStack = document.elementsFromPoint(centerX, centerY) || [];
                    centerStack.forEach((el, stackIndex) => {
                        let node = el;
                        let depth = 0;
                        while (node && node !== document.body && depth < 8) {
                            pushContainer(node, `center_stack_${stackIndex}_${depth}`);
                            node = node.parentElement;
                            depth += 1;
                        }
                    });
                    const explicit = [
                        document.querySelector("[data-e2e='feed-active-video']"),
                        document.querySelector("main"),
                        document.querySelector("article"),
                    ];
                    explicit.forEach((el, idx) => pushContainer(el, `explicit_${idx}`));
                    containers.sort((a, b) => b.score - a.score);
                    const active =
                        containers.find((item) => item.anchorHits > 0 && item.hintHits >= 1 && item.footerHits === 0) ||
                        containers.find((item) => item.mediaHits > 0 && item.hintHits >= 1 && item.footerHits === 0) ||
                        containers.find((item) => item.hintHits >= 2 && item.footerHits === 0) ||
                        containers.find((item) => (item.text.includes('点赞') || item.text.includes('评论') || item.text.includes('收藏') || item.text.includes('分享')) && item.footerHits === 0) ||
                        containers[0] ||
                        null;

                    const scope = active && active.element ? active.element : document.body;
                    const isSelfUserHref = (href) => {
                        const lowered = String(href || '').toLowerCase();
                        return lowered.includes('/user/self') || lowered.includes('sec_user_id=self');
                    };
                    const anchors = [...scope.querySelectorAll("a[href]")].filter(isVisible).map((anchor) => {
                        const rect = anchor.getBoundingClientRect();
                        const activeRect = active ? active.rect : { left: centerX - 10, top: centerY - 10, width: 20, height: 20 };
                        const withinActiveBox =
                            rect.right >= activeRect.left - 80 &&
                            rect.left <= activeRect.left + activeRect.width + 80 &&
                            rect.bottom >= activeRect.top - 80 &&
                            rect.top <= activeRect.top + activeRect.height + 80;
                        return {
                            href: anchor.href,
                            text: cleanText(anchor.innerText || anchor.getAttribute('aria-label') || anchor.title || ''),
                            distance: Math.abs(rect.left + rect.width / 2 - centerX) + Math.abs(rect.top + rect.height / 2 - (active ? active.rect.top + Math.min(active.rect.height * 0.45, active.rect.height - 20) : centerY)),
                            area: rect.width * rect.height,
                            withinActiveBox,
                        };
                    }).sort((a, b) => a.distance - b.distance || b.area - a.area);

                    const videoLink = anchors.find((anchor) => anchor.href.includes('/video/') && anchor.withinActiveBox) || anchors.find((anchor) => anchor.href.includes('/video/')) || null;
                    const creatorAnchors = anchors.filter((anchor) => anchor.href.includes('/user/') && !isSelfUserHref(anchor.href));
                    const creatorLink =
                        creatorAnchors.find((anchor) => anchor.withinActiveBox && anchor.text) ||
                        creatorAnchors.find((anchor) => anchor.withinActiveBox) ||
                        creatorAnchors.find((anchor) => anchor.text) ||
                        creatorAnchors[0] ||
                        null;
                    const rect = active ? active.rect : { left: centerX - 10, top: centerY - 10, width: 20, height: 20 };
                    return {
                        active_text: active ? active.text : cleanText(document.body?.innerText || ''),
                        container_hint: active ? active.source : null,
                        video_url: videoLink ? videoLink.href : null,
                        creator_profile_url: creatorLink ? creatorLink.href : null,
                        creator_name: creatorLink ? creatorLink.text : null,
                        interaction_x: Math.max(20, Math.min(window.innerWidth - 20, rect.left + rect.width / 2)),
                        interaction_y: Math.max(20, Math.min(window.innerHeight - 20, rect.top + Math.min(rect.height * 0.45, rect.height - 20))),
                    };
                }""",
                selectors.FEED_TEXT_HINTS,
                selectors.GLOBAL_CHROME_HINTS,
                selectors.LEGAL_FOOTER_HINTS,
            )
        except Exception:
            return None

        active_text = (state or {}).get("active_text") if isinstance(state, dict) else None
        if not active_text:
            return None
        creator_profile_url = _normalize_url((state or {}).get("creator_profile_url"))
        if self._looks_like_self_profile(creator_profile_url):
            state["creator_profile_url"] = None
            state["creator_name"] = None
        if _looks_like_global_page_chrome(active_text):
            return None
        if not any(hint in active_text for hint in selectors.FEED_TEXT_HINTS):
            return None
        return state

    def _current_feed_identity(self) -> str | None:
        state = self._extract_active_feed_state()
        if state is None:
            return None
        return _state_identity(state)

    @staticmethod
    def _candidate_identity(candidate: FeedCandidateSnapshot | None) -> str | None:
        if candidate is None:
            return None
        return candidate.feed_identity or _normalize_url(candidate.video_url) or candidate.caption_text or candidate.total_interaction_text

    def _capture(self, label: str, full_page: bool = False) -> str | None:
        path = self.artifacts.screenshot_path(label)

        try:
            self.page.screenshot(
                path=str(path),
                full_page=full_page,
                timeout=2_500,
                animations="disabled",
                caret="hide",
            )
            return str(path)

        except OSError as exc:
            if getattr(exc, "errno", None) == 28:
                self.logger.warning(
                    "disk space is full; skip screenshot",
                    extra={
                        "label": label,
                        "path": str(path),
                        "error": str(exc),
                    },
                )
                return None
            raise

        except Exception as exc:
            self.logger.warning("Non-fatal screenshot failure for %s: %s", label, exc)
            return None
        
    #添加校验函数
    def _validate_video_url_against_active_text(self, video_url: str | None, creator_name: str | None, active_text_summary: str | None, debug_label: str | None = None,) -> bool:
        """Check whether a captured video_url really matches the current active feed item.

        Network-captured video URLs can be stale or belong to preloaded/recommended videos.
        This method opens the video URL in a temporary tab and checks whether the page text
        contains the expected creator name and important words from the active feed text.
        """
        if not video_url:
            return False

        detail_page = None

        try:
            detail_page = self.page.context.new_page()
            detail_page.goto(video_url, wait_until="domcontentloaded", timeout=45_000)
            detail_page.wait_for_timeout(2_000)

            try:
                body_text = detail_page.locator("body").inner_text(timeout=5_000)
            except Exception:
                body_text = ""

            body_text = " ".join(body_text.split())
            active_text = " ".join((active_text_summary or "").split())

            if not body_text:
                return False

            # 1. 作者名必须匹配。作者名不匹配，基本就是错的链接。
            if creator_name and creator_name not in body_text:
                self.logger.info(
                    "network video_url rejected because creator does not match",
                    extra={
                        "video_url": video_url,
                        "creator_name": creator_name,
                        "debug_label": debug_label,
                    },
                )
                return False

            # 2. 从当前推荐流文本里抽几个关键词，要求单视频页至少命中一部分。
            keywords = self._extract_validation_keywords(active_text)

            if not keywords:
                # 没有关键词时，只要作者名匹配就先接受。
                return bool(creator_name and creator_name in body_text)

            matched_keywords = [word for word in keywords if word in body_text]

            # 至少命中 2 个关键词，或者关键词很少时命中 1 个。
            required_matches = 1 if len(keywords) <= 2 else 2

            is_valid = len(matched_keywords) >= required_matches

            if not is_valid:
                self.logger.info(
                    "network video_url rejected because text does not match active card",
                    extra={
                        "video_url": video_url,
                        "creator_name": creator_name,
                        "keywords": keywords,
                        "matched_keywords": matched_keywords,
                        "debug_label": debug_label,
                    },
                )

            return is_valid

        except Exception as exc:
            self.logger.info(
                "network video_url validation failed",
                extra={
                    "video_url": video_url,
                    "creator_name": creator_name,
                    "debug_label": debug_label,
                    "error": str(exc),
                },
            )
            return False

        finally:
            if detail_page is not None:
                try:
                    detail_page.close()
                except Exception:
                    pass
    #提炼验证关键词
    def _extract_validation_keywords(self, text: str | None) -> list[str]:
        """Extract useful keywords from active feed text for video URL validation."""
        if not text:
            return []

        cleaned = " ".join(text.split())

        noise_phrases = [
            "发送",
            "倍速",
            "智能",
            "清屏",
            "连播",
            "详情",
            "TA的作品",
            "评论",
            "问AI",
            "相关推荐",
            "大家都在搜",
            "全部评论",
            "听抖音",
            "认证徽章",
            "分享",
            "回复",
            "展开",
            "暂时没有更多评论",
            "留下你的精彩评论吧",
            "加载中",
        ]

        for phrase in noise_phrases:
            cleaned = cleaned.replace(phrase, " ")

        cleaned = re.sub(r"\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}", " ", cleaned)
        cleaned = re.sub(r"https?://\S+", " ", cleaned)
        cleaned = re.sub(r"[@#·，。！？、:：|｜()\[\]【】《》“”\"']", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        words: list[str] = []

        for token in cleaned.split():
            token = token.strip()
            if not token:
                continue

            if len(token) < 2:
                continue

            if token.replace(".", "").isdigit():
                continue

            if re.fullmatch(r"\d+(\.\d+)?[万亿wWkK]?", token):
                continue

            words.append(token)

        return words[:8]
    
    #按 Escape 关闭评论面板/商品卡,  点击视频中间区域，让当前视频重新获得焦点,  如果页面里还有商品/评论遮挡，记录日志
    def _prepare_feed_focus_before_homepage_open(
    self,
    debug_label: str | None = None,
    ) -> None:
        """Close comment/product overlays and refocus the active video before pressing F.

        Shopping/product cards and comment panels can steal keyboard focus.
        If focus stays inside those overlays, pressing F may not open the creator homepage.
        """
        # 1. 先尝试按 Escape，关闭评论面板、商品卡、弹层
        for _ in range(3):
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(350)
            except Exception:
                pass

        # 2. 再尝试点击视频中心区域，把焦点还给当前视频
        try:
            viewport = self.page.viewport_size or {"width": 1440, "height": 900}
            x = int(viewport["width"] * 0.42)
            y = int(viewport["height"] * 0.50)
            self.page.mouse.click(x, y)
            self.page.wait_for_timeout(500)
        except Exception as exc:
            self.logger.info(
                "failed to refocus feed before homepage open",
                extra={
                    "debug_label": debug_label,
                    "error": str(exc),
                },
            )

        # 3. 如果页面里还有明显的商品/评论遮挡，再记录日志
        try:
            body_text = self.page.locator("body").inner_text(timeout=1500)
        except Exception:
            body_text = ""

        overlay_hints = [
            "视频同款",
            "购物",
            "选择",
            "运费险",
            "7天无理由",
            "全部评论",
            "留下你的精彩评论吧",
        ]

        if any(hint in body_text for hint in overlay_hints):
            self.logger.info(
                "feed may still contain product/comment overlay before F-key homepage open",
                extra={
                    "debug_label": debug_label,
                    "overlay_hints": [hint for hint in overlay_hints if hint in body_text],
                },
            )
            
    def _copy_current_video_share_link(
        self,
        debug_label: str | None = None,
    ) -> str | None:
        """Copy the stable share link of the current active Douyin video.

        This uses the UI share button + copy link button.
        We grant clipboard permission before reading navigator.clipboard.readText(),
        otherwise Chrome may raise Read permission denied.
        """
        try:
            # 0. 先给当前 Douyin 页面授权剪贴板读取/写入权限
            try:
                self.page.context.grant_permissions(
                    ["clipboard-read", "clipboard-write"],
                    origin="https://www.douyin.com",
                )
            except Exception as exc:
                self.logger.info(
                    "failed to grant clipboard permissions",
                    extra={
                        "debug_label": debug_label,
                        "error": str(exc),
                    },
                )

            # 1. 先关闭评论面板、商品弹层、其他浮层，避免挡住分享按钮
            for _ in range(2):
                try:
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(300)
                except Exception:
                    pass

            # 2. 点击右侧分享按钮
            clicked_share = self._click_current_video_share_button(debug_label=debug_label)

            if not clicked_share:
                self.logger.info(
                    "share button not found; skip copying current video link",
                    extra={
                        "debug_label": debug_label,
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                    },
                )
                return None

            self.page.wait_for_timeout(1500)

            # 3. 如果 selector 找不到，使用较保守的右侧区域坐标兜底
            # 注意：这个坐标可能需要根据你的屏幕微调。
            if not clicked_share:
                self.logger.info(
                    "share button not found; skip copying current video link",
                    extra={
                        "debug_label": debug_label,
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                    },
                )
                return None

            self.page.wait_for_timeout(1500)

            # 4. 点击“复制链接”按钮
            copy_button_candidates = [
                'text=复制链接',
                'text=复制口令',
                'button:has-text("复制链接")',
                'button:has-text("复制口令")',
                'div[role="button"]:has-text("复制链接")',
                'div[role="button"]:has-text("复制口令")',
                'div:has-text("复制链接")',
                'div:has-text("复制口令")',
                '[aria-label*="复制"]',
                '[title*="复制"]',
            ]

            clicked_copy = False

            for selector in copy_button_candidates:
                try:
                    locator = self.page.locator(selector).first
                    if locator.count() > 0 and locator.is_visible(timeout=1000):
                        locator.click(timeout=2000)
                        clicked_copy = True
                        self.logger.info(
                            "copy link button clicked",
                            extra={
                                "debug_label": debug_label,
                                "selector": selector,
                            },
                        )
                        break
                except Exception:
                    continue

            if not clicked_copy:
                try:
                    share_panel_text = self.page.locator("body").inner_text(timeout=1500)
                except Exception:
                    share_panel_text = ""

                self.logger.info(
                    "copy link button not found after opening share panel",
                    extra={
                        "debug_label": debug_label,
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                        "share_panel_text": _summarize_text(share_panel_text, limit=500),
                    },
                )
                return None

            self.page.wait_for_timeout(800)

            # 5. 读取剪贴板
            try:
                copied_text = self.page.evaluate("navigator.clipboard.readText()")
            except Exception as exc:
                self.logger.info(
                    "failed to read clipboard after copy button clicked",
                    extra={
                        "debug_label": debug_label,
                        "error": str(exc),
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                    },
                )
                return None

            # 6. 从复制出来的文字里提取真正的 douyin 链接
            match = re.search(r"https?://[^\s]+douyin\.com/[^\s]+", copied_text or "")
            share_link = match.group(0).strip() if match else None

            if not share_link:
                self.logger.info(
                    "copied text does not contain a douyin link",
                    extra={
                        "debug_label": debug_label,
                        "copied_text": copied_text,
                        "page_url": self.page.url,
                        "page_title": self._safe_title(),
                    },
                )
                return None

            self.logger.info(
                "current video share link copied",
                extra={
                    "debug_label": debug_label,
                    "share_link": share_link,
                },
            )

            return share_link

        except Exception as exc:
            self.logger.info(
                "failed to copy current video share link",
                extra={
                    "debug_label": debug_label,
                    "error": str(exc),
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )
            return None

        finally:
            # 7. 最后尝试关闭分享面板
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(300)
            except Exception:
                pass
    
    def _click_current_video_share_button( #点击分享按钮
        self,
        debug_label: str | None = None,
    ) -> bool:
        """Click the share button of the current visible feed video.

        This avoids broad selectors like div:has-text("分享").
        It searches only small clickable elements on the right side of the viewport.
        """
        try:
            result = self.page.evaluate(
                """
                () => {
                    const vw = window.innerWidth || document.documentElement.clientWidth;
                    const vh = window.innerHeight || document.documentElement.clientHeight;

                    function isVisible(el) {
                        const style = window.getComputedStyle(el);
                        if (!style) return false;
                        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
                            return false;
                        }

                        const rect = el.getBoundingClientRect();
                        if (!rect || rect.width <= 0 || rect.height <= 0) return false;

                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;

                        if (cx < 0 || cx > vw || cy < 0 || cy > vh) return false;

                        return true;
                    }

                    function textOf(el) {
                        return [
                            el.innerText || "",
                            el.textContent || "",
                            el.getAttribute("aria-label") || "",
                            el.getAttribute("title") || "",
                            el.getAttribute("data-e2e") || "",
                            el.getAttribute("class") || "",
                        ].join(" ");
                    }

                    function clickableParent(el) {
                        let cur = el;
                        for (let i = 0; i < 5 && cur; i++) {
                            const tag = (cur.tagName || "").toLowerCase();
                            const role = cur.getAttribute("role") || "";
                            const onclick = cur.getAttribute("onclick") || "";
                            const tabIndex = cur.getAttribute("tabindex");

                            if (
                                tag === "button" ||
                                tag === "a" ||
                                role === "button" ||
                                onclick ||
                                tabIndex !== null
                            ) {
                                return cur;
                            }

                            cur = cur.parentElement;
                        }

                        return el;
                    }

                    const rawElements = Array.from(
                        document.querySelectorAll(
                            'button, a, [role="button"], [aria-label], [title], [data-e2e], svg, path, div, span'
                        )
                    );

                    const candidates = [];

                    for (const raw of rawElements) {
                        const el = clickableParent(raw);
                        if (!el || !isVisible(el)) continue;

                        const rect = el.getBoundingClientRect();

                        // 只要右侧区域，避免点左侧导航/页脚
                        if (rect.left < vw * 0.58) continue;

                        // 排除顶部浏览器/导航附近、底部边缘
                        if (rect.top < 80 || rect.bottom > vh - 20) continue;

                        // 排除大块容器，只保留像按钮的小元素
                        if (rect.width > 180 || rect.height > 180) continue;
                        if (rect.width < 8 || rect.height < 8) continue;

                        const text = textOf(el);
                        const lower = text.toLowerCase();

                        const looksLikeShare =
                            text.includes("分享") ||
                            text.includes("转发") ||
                            lower.includes("share") ||
                            lower.includes("forward");

                        if (!looksLikeShare) continue;

                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;

                        let score = 0;

                        // 越靠右越像视频右侧按钮栏
                        score += cx / vw * 100;

                        // 不要太靠顶部，也不要太靠底部
                        score -= Math.abs(cy - vh * 0.62) / 8;

                        const tag = (el.tagName || "").toLowerCase();
                        const role = el.getAttribute("role") || "";
                        const dataE2E = el.getAttribute("data-e2e") || "";
                        const ariaLabel = el.getAttribute("aria-label") || "";

                        if (tag === "button") score += 30;
                        if (role === "button") score += 25;
                        if (dataE2E.includes("share")) score += 50;
                        if (ariaLabel.includes("分享")) score += 50;
                        if (text.trim() === "分享") score += 40;

                        candidates.push({
                            el,
                            score,
                            tag,
                            role,
                            dataE2E,
                            ariaLabel,
                            text: text.trim().slice(0, 80),
                            rect: {
                                left: Math.round(rect.left),
                                top: Math.round(rect.top),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                            },
                        });
                    }

                    candidates.sort((a, b) => b.score - a.score);

                    const debugCandidates = candidates.slice(0, 8).map(c => ({
                        score: Math.round(c.score),
                        tag: c.tag,
                        role: c.role,
                        dataE2E: c.dataE2E,
                        ariaLabel: c.ariaLabel,
                        text: c.text,
                        rect: c.rect,
                    }));

                    if (candidates.length === 0) {
                        return {
                            clicked: false,
                            reason: "no_share_candidate",
                            candidates: debugCandidates,
                        };
                    }

                    const best = candidates[0];
                    best.el.click();

                    return {
                        clicked: true,
                        reason: "clicked_best_share_candidate",
                        best: {
                            score: Math.round(best.score),
                            tag: best.tag,
                            role: best.role,
                            dataE2E: best.dataE2E,
                            ariaLabel: best.ariaLabel,
                            text: best.text,
                            rect: best.rect,
                        },
                        candidates: debugCandidates,
                    };
                }
                """
            )

            if result.get("clicked"):
                self.logger.info(
                    "share button clicked by current-video candidate",
                    extra={
                        "debug_label": debug_label,
                        "best": result.get("best"),
                        "candidates": result.get("candidates"),
                    },
                )
                return True

            self.logger.info(
                "share button not found by current-video candidate search",
                extra={
                    "debug_label": debug_label,
                    "reason": result.get("reason"),
                    "candidates": result.get("candidates"),
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )
            return False

        except Exception as exc:
            self.logger.info(
                "failed to click current video share button",
                extra={
                    "debug_label": debug_label,
                    "error": str(exc),
                    "page_url": self.page.url,
                    "page_title": self._safe_title(),
                },
            )
            return False

    def _open_creator_homepage_by_url(
    self,
    creator_profile_url: str | None,
    debug_label: str | None = None,
    ) -> PageStateSnapshot:
        """Open creator homepage directly when F-key fails.

        Product cards / shopping panels often steal focus, so pressing F may not
        open the creator homepage. If we already know the creator profile URL,
        direct navigation is safer.
        """
        if not creator_profile_url:
            return self.classify_page_state(
                debug_label=f"{debug_label}_direct_homepage_missing_url" if debug_label else "direct_homepage_missing_url",
                capture=True,
            )

        self.logger.info(
            "opening creator homepage by direct profile URL",
            extra={
                "creator_profile_url": creator_profile_url,
                "page_url": self.page.url,
                "page_title": self._safe_title(),
                "debug_label": debug_label,
            },
        )

        self.page.goto(
            creator_profile_url,
            wait_until="domcontentloaded",
            timeout=45_000,
        )
        self.page.wait_for_timeout(2_000)

        return self.classify_page_state(
            debug_label=f"{debug_label}_homepage_direct_url" if debug_label else "homepage_direct_url",
            capture=True,
        )


#DouyinPageAdapter class ends before this line
def _extract_aweme_items(payload: dict | list) -> list[dict[str, str | None]]:
    items: list[dict[str, str | None]] = []
    for node in _walk_json_nodes(payload):
        if not isinstance(node, dict):
            continue
        video_id = _normalize_video_id(
            node.get("aweme_id")
            or node.get("group_id")
            or node.get("item_id")
            or _dig(node, "statistics", "aweme_id")
        )
        if not video_id:
            continue
        creator_name = _sanitize_creator_name(
            _dig(node, "author", "nickname")
            or _dig(node, "user", "nickname")
            or _dig(node, "author_info", "nickname")
        )
        sec_uid = _dig(node, "author", "sec_uid") or _dig(node, "user", "sec_uid")
        uid = _dig(node, "author", "uid") or _dig(node, "user", "uid")
        creator_profile_url = None
        if sec_uid:
            creator_profile_url = f"https://www.douyin.com/user/{sec_uid}"
        elif uid:
            creator_profile_url = f"https://www.douyin.com/user/{uid}"
        description = (
            node.get("desc")
            or node.get("description")
            or node.get("title")
            or _dig(node, "share_info", "share_desc")
        )
        if not any((creator_name, creator_profile_url, description)):
            continue
        items.append(
            {
                "video_id": video_id,
                "video_url": f"https://www.douyin.com/video/{video_id}",
                "creator_name": creator_name,
                "creator_profile_url": _normalize_url(creator_profile_url),
                "description": description,
            }
        )
    return items


def _extract_comment_threads(payload: dict | list, fallback_video_id: str | None = None) -> list[tuple[str, list[CommentSnippet]]]:
    pairs: list[tuple[str, list[CommentSnippet]]] = []
    global_video_id = fallback_video_id or _extract_primary_video_id(payload)
    for node in _walk_json_nodes(payload):
        if not isinstance(node, dict):
            continue
        comments = node.get("comments")
        if not isinstance(comments, list) or not comments:
            continue
        video_id = _normalize_video_id(
            node.get("aweme_id")
            or node.get("item_id")
            or node.get("group_id")
            or _dig(node, "data", "aweme_id")
            or _dig(node, "aweme", "aweme_id")
            or _dig(node, "comment_info", "aweme_id")
            or _dig(node, "aweme_detail", "aweme_id")
        ) or global_video_id
        if not video_id:
            continue
        snippets: list[CommentSnippet] = []
        for comment in comments[:8]:
            if not isinstance(comment, dict):
                continue
            text = _clean_comment_text(comment.get("text"))
            if not text:
                continue
            snippets.append(
                CommentSnippet(
                    author_name=_sanitize_creator_name(
                        _dig(comment, "user", "nickname")
                        or _dig(comment, "author", "nickname")
                    ),
                    text=text,
                    like_count_raw=_stringify_number(comment.get("digg_count")),
                    source="network",
                )
            )
        if snippets:
            pairs.append((video_id, snippets))
    return pairs


def _extract_primary_video_id(payload: dict | list) -> str | None:
    for node in _walk_json_nodes(payload):
        if not isinstance(node, dict):
            continue
        video_id = _normalize_video_id(
            node.get("aweme_id")
            or node.get("item_id")
            or node.get("group_id")
            or _dig(node, "data", "aweme_id")
            or _dig(node, "aweme", "aweme_id")
            or _dig(node, "aweme_detail", "aweme_id")
        )
        if video_id:
            return video_id
    return None


def _extract_video_id_from_response_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("aweme_id", "item_id", "group_id", "modal_id", "video_id"):
        values = query.get(key, [])
        if not values:
            continue
        video_id = _normalize_video_id(values[0])
        if video_id:
            return video_id
    return None


def _walk_json_nodes(payload):
    stack = [payload]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _dig(node: dict, *path: str):
    current = node
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _normalize_video_id(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d{8,})", text)
    return match.group(1) if match else None


def _extract_video_id_from_url(url: str | None) -> str | None:
    raw = url.strip() if isinstance(url, str) else url
    normalized = _normalize_url(url)
    if not normalized:
        return None
    match = re.search(r"/video/(\d{8,})", normalized)
    if match:
        return match.group(1)
    parsed = urlparse(raw or normalized)
    params = parse_qs(parsed.query)
    for key in ("video_id", "aweme_id", "item_id"):
        values = params.get(key)
        if values:
            normalized_id = _normalize_video_id(values[0])
            if normalized_id:
                return normalized_id
    return None


def _strip_inline_noise(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = str(text)
    for hint in selectors.INLINE_NOISE_HINTS:
        cleaned = cleaned.replace(hint, " ")
    cleaned = cleaned.replace("。。。", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _clean_metadata_lines(text: str | None) -> list[str]:
    cleaned_text = _strip_inline_noise(text)
    if not cleaned_text:
        return []
    normalized_text = cleaned_text
    for token in ("作者声明：", "作者声明:", "相关搜索：", "相关搜索:", "章节要点", "下一章", "下一集"):
        normalized_text = normalized_text.replace(token, f"\n{token}")
    for token in ("详情", "TA的作品", "问AI", "相关推荐", "大家都在搜", "全部评论", "识别画面", "顺序连播", "正在播放"):
        normalized_text = normalized_text.replace(token, f"\n{token}\n")
    normalized_text = re.sub(r"(第\d+[章节集期回](?:[:：]))", r"\n\1", normalized_text)
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in re.split(r"\n+", normalized_text):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line in seen:
            continue
        if len(line) <= 2:
            continue
        if line in selectors.GLOBAL_CHROME_HINTS or line in selectors.FEED_TEXT_HINTS:
            continue
        if any(hint in line for hint in selectors.METADATA_NOISE_HINTS):
            continue
        if any(hint in line for hint in selectors.LEGAL_FOOTER_HINTS):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?[万亿wWkK]?", line):
            continue
        if re.fullmatch(r"\(\d+\)", line):
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}", line):
            continue
        line = _strip_feed_metric_prefix(line)
        if not line:
            continue
        lines.append(line)
        seen.add(line)
    return lines


def _clean_video_description_text(text: str | None, limit: int = 360) -> str | None:
    lines = _clean_metadata_lines(text)
    if not lines:
        return None
    filtered_lines = [
        line
        for line in lines
        if not any(token in line for token in ("下一章", "下一集", "章节要点"))
    ]
    if not filtered_lines:
        return None
    return _summarize_text(" ".join(_strip_feed_metric_prefix(line) or "" for line in filtered_lines), limit=limit)


def _extract_video_title_text(text: str | None) -> str | None:
    lines = _clean_metadata_lines(text)
    if not lines:
        return None
    primary_lines = lines[:2]
    cleaned = " ".join(primary_lines)
    cleaned = _strip_feed_metric_prefix(cleaned) or cleaned
    cleaned = re.sub(r"^@[^·\s]+(?:\s*·\s*[^ ]+)?\s*", "", cleaned).strip()
    cleaned = re.sub(r"相关搜索[:：].*$", "", cleaned).strip()
    cleaned = re.sub(r"作者声明[:：].*$", "", cleaned).strip()
    if not cleaned:
        return None
    return _summarize_text(cleaned, limit=160)


def _extract_chapter_texts(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = _strip_inline_noise(text) or ""
    matches = re.findall(
        r"(第\d+[章节集期回](?:[:：][^\s#。！？，,；;\n]{1,20})?)",
        cleaned,
    )
    if "章节要点" in cleaned:
        matches.append("章节要点")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in matches:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)
    return deduped[:8]


def _extract_related_search_terms(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = _strip_inline_noise(text) or ""
    cleaned = cleaned.replace("作者声明：", "\n作者声明：").replace("作者声明:", "\n作者声明:")
    terms: list[str] = []
    for match in re.finditer(r"相关搜索[:：]\s*([^\n。！？#]+)", cleaned):
        raw_terms = re.split(r"[、,/| ]+", match.group(1).strip())
        for item in raw_terms:
            normalized = item.strip()
            if normalized and normalized not in terms:
                terms.append(normalized)
    return terms[:6]


def _extract_author_statement_texts(text: str | None) -> list[str]:
    if not text:
        return []
    cleaned = _strip_inline_noise(text) or ""
    statements: list[str] = []
    for match in re.finditer(r"作者声明[:：]\s*([^\n。！？]{1,80})", cleaned):
        statement = f"作者声明：{match.group(1).strip()}"
        if statement not in statements:
            statements.append(statement)
    for hint in selectors.AUTHOR_STATEMENT_HINTS:
        if hint.endswith(":") or hint.endswith("："):
            continue
        if hint in cleaned and hint not in statements:
            statements.append(hint)
    return statements[:6]


def _build_video_text_bundle(
    *,
    title_text: str | None,
    description_text: str | None,
    expanded_description_text: str | None,
    chapter_texts: list[str],
    related_search_terms: list[str],
    author_statement_texts: list[str],
    visible_subtitle_segments: list[str],
    top_comments: list[CommentSnippet],
) -> str | None:
    deduped_title = title_text if _is_meaningfully_distinct(title_text, description_text, expanded_description_text) else None
    deduped_expanded = (
        expanded_description_text
        if _is_meaningfully_distinct(expanded_description_text, description_text)
        else None
    )
    sections = [
        f"标题：{deduped_title}" if deduped_title else None,
        f"简介：{description_text}" if description_text else None,
        f"扩展简介：{deduped_expanded}" if deduped_expanded else None,
        f"章节：{' | '.join(chapter_texts)}" if chapter_texts else None,
        f"相关搜索：{' | '.join(challenge for challenge in related_search_terms if challenge)}" if related_search_terms else None,
        f"作者声明：{' | '.join(statement for statement in author_statement_texts if statement)}" if author_statement_texts else None,
        f"可见字幕：{' | '.join(segment for segment in visible_subtitle_segments if segment)}" if visible_subtitle_segments else None,
        (
            "评论："
            + " | ".join(
                f"{comment.author_name or '匿名'}:{comment.text}"
                for comment in top_comments[:5]
            )
        )
        if top_comments
        else None,
    ]
    return _summarize_text("；".join(part for part in sections if part), limit=1200)


def _extract_visible_subtitle_sample(text: str | None) -> list[str]:
    lines = _clean_metadata_lines(text)
    segments: list[str] = []
    for line in lines:
        if len(line) < 4 or len(line) > 32:
            continue
        if line.startswith("@") or "相关搜索" in line or "作者声明" in line:
            continue
        if any(token in line for token in ("点赞", "评论", "收藏", "分享", "下一章", "下一集", "章节要点")):
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?[万亿wWkK]?", line):
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}", line):
            continue
        segments.append(line)
    return segments[:4]


def _merge_subtitle_segments(existing: list[str], incoming: list[str], limit: int = 6) -> list[str]:
    merged = list(existing)
    seen = {item.strip() for item in existing if item.strip()}
    for item in incoming:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        merged.append(normalized)
        seen.add(normalized)
        if len(merged) >= limit:
            break
    return merged[:limit]


def _clean_comment_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < 4:
        return None
    if any(token in cleaned for token in ("点赞", "回复", "查看更多", "展开")) and len(cleaned) <= 8:
        return None
    return cleaned


def _merge_comment_snippets(
    network_comments: list[CommentSnippet],
    ui_comments: list[CommentSnippet],
    limit: int = 5,
) -> list[CommentSnippet]:
    merged: list[CommentSnippet] = []
    seen: set[str] = set()
    for comment in [*network_comments, *ui_comments]:
        text = _clean_comment_text(comment.text)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        merged.append(
            CommentSnippet(
                author_name=comment.author_name,
                text=text,
                like_count_raw=comment.like_count_raw,
                source=comment.source,
            )
        )
        seen.add(key)
        if len(merged) >= limit:
            break
    return merged


def _build_comment_collection_result(
    *,
    network_comments: list[CommentSnippet],
    ui_comments: list[CommentSnippet],
    triggered: bool,
    panel_visible: bool,
    parse_failed: bool,
    network_url: str | None,
) -> CommentCollectionResult:
    merged = _merge_comment_snippets(network_comments, ui_comments)
    if network_comments and ui_comments:
        source = "mixed"
    elif network_comments:
        source = "network"
    elif ui_comments:
        source = "ui"
    else:
        source = "none"

    if merged:
        status = "success"
    elif parse_failed:
        status = "parse_failed"
    elif not triggered:
        status = "panel_open_failed"
    elif panel_visible and not network_comments and not ui_comments:
        status = "panel_empty"
    else:
        status = "network_miss"

    debug_parts = [
        f"comment_api={network_url}" if network_url else None,
        f"panel_visible={str(panel_visible).lower()}",
        f"network_count={len(network_comments)}",
        f"ui_count={len(ui_comments)}",
        "ui_parse_failed" if parse_failed else None,
    ]
    return CommentCollectionResult(
        comments=merged,
        source=source,
        status=status,
        debug=";".join(part for part in debug_parts if part),
        network_count=len(network_comments),
        ui_count=len(ui_comments),
        panel_visible=panel_visible,
        network_url=network_url,
    )


def _merge_description_text(primary: str | None, fallback: str | None) -> str | None:
    if primary and fallback:
        if primary == fallback:
            return primary
        if _text_overlap_score(primary, fallback) >= 0.7:
            return primary if len(primary) >= len(fallback) else fallback
        return _summarize_text(f"{primary} {fallback}", limit=360)
    return primary or fallback


def _text_overlap_score(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    left_tokens = {token for token in re.split(r"[\s#@·•|，。！？、]+", left) if len(token) >= 2}
    right_tokens = {token for token in re.split(r"[\s#@·•|，。！？、]+", right) if len(token) >= 2}
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    baseline = max(1, min(len(left_tokens), len(right_tokens)))
    return len(overlap) / baseline


def _stringify_number(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _contains_any(text: str | None, phrases: list[str]) -> bool:
    haystack = (text or "").lower()
    return any(phrase.lower() in haystack for phrase in phrases)


def _extract_metric(text: str, label: str) -> str | None:
    patterns = [
        rf"{label}\s*([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)",
        rf"([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)\s*{label}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_publish_time(text: str) -> str | None:
    patterns = [
        r"\d+\s*天前",
        r"\d+\s*小时前",
        r"\d+\s*分钟前",
        r"\d{1,2}月\d{1,2}日",
        r"昨天",
        r"前天",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _extract_followers(text: str) -> str | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)\s*粉丝", text)
    if match:
        return match.group(1)
    match = re.search(r"粉丝[:：]?\s*([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)", text)
    return match.group(1) if match else None


def _extract_total_likes(text: str) -> str | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)\s*总获赞", text)
    if match:
        return match.group(1)
    match = re.search(r"([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)\s*获赞", text)
    if match:
        return match.group(1)
    match = re.search(r"总获赞[:：]?\s*([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)", text)
    if match:
        return match.group(1)
    match = re.search(r"获赞[:：]?\s*([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)", text)
    if match:
        return match.group(1)
    match = re.search(r"点赞[:：]?\s*([0-9]+(?:\.[0-9]+)?[万亿wWkK]?)", text)
    return match.group(1) if match else None


def _extract_creator_name(text: str | None) -> str | None:
    if not text:
        return None
    handle_match = re.search(r"@([^\n·•#]+)", text)
    if handle_match:
        return _sanitize_creator_name(handle_match.group(1))
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if any(token in cleaned for token in ("点赞", "评论", "收藏", "分享", "听抖音", "广告")):
            continue
        sanitized = _sanitize_creator_name(cleaned)
        if sanitized and len(sanitized) <= 32:
            return sanitized
    return None


def _extract_profile_panel_name(text: str | None) -> str | None:
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines[:6]):
        if line == "@" and index + 1 < len(lines):
            candidate = _sanitize_creator_name(lines[index + 1])
            if candidate:
                return candidate
        if line.startswith("@"):
            candidate = _sanitize_creator_name(line)
            if candidate:
                return candidate
    for line in lines[:6]:
        if any(token in line for token in ("粉丝", "获赞", "关注", "TA的作品", "评论", "合集", "问AI", "加载中", "正在播放")):
            continue
        candidate = _sanitize_creator_name(line)
        if candidate:
            return candidate
    return None


def _extract_metric_pack(text: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    if not text:
        return (None, None, None, None)
    leading = text.split("听抖音", 1)[0]
    leading = re.sub(r"\b\d{1,2}:\d{2}\b", " ", leading)
    numbers = re.findall(r"\d+(?:\.\d+)?[万亿wWkK]?", leading)
    if len(numbers) < 4:
        return (None, None, None, None)
    like_count, comment_count, favorite_count, share_count = numbers[-4:]
    return (like_count, comment_count, favorite_count, share_count)


def _sanitize_creator_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = name.strip().lstrip("@").strip()
    if "\n" in cleaned:
        lines = [
            line.strip().lstrip("@").strip()
            for line in cleaned.splitlines()
            if line.strip() and line.strip() != "@"
        ]
        if lines:
            cleaned = lines[0]
    cleaned = re.split(r"[·•|#]", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.replace("TA的作品", "").replace("详情", "").strip()
    if not cleaned:
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}", cleaned):
        return None
    if re.fullmatch(r"(?:\d+(?:\.\d+)?[万亿wWkK]?\s*){2,4}", cleaned):
        return None
    lowered = cleaned.lower()
    if "@" in cleaned:
        return None
    if re.fullmatch(r"[a-z0-9._-]+\.(com|cn|net|org|io)", lowered):
        return None
    generic_names = {
        "我的",
        "推荐",
        "精选",
        "关注",
        "朋友",
        "直播",
        "放映厅",
        "短剧",
        "小游戏",
        "作品",
        "合集",
        "评论",
        "详情",
        "问ai",
        "相关推荐",
        "搜索",
    }
    if lowered in generic_names:
        return None
    return cleaned


def _normalize_text_for_compare(text: str | None) -> str:
    if not text:
        return ""
    normalized = _strip_inline_noise(text) or ""
    normalized = _strip_feed_metric_prefix(normalized) or normalized
    normalized = re.sub(r"\b\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ；;，,。.")
    return normalized


def _is_meaningfully_distinct(candidate: str | None, *references: str | None) -> bool:
    normalized_candidate = _normalize_text_for_compare(candidate)
    if not normalized_candidate:
        return False
    for reference in references:
        normalized_reference = _normalize_text_for_compare(reference)
        if not normalized_reference:
            continue
        if normalized_candidate == normalized_reference:
            return False
        if normalized_candidate in normalized_reference or normalized_reference in normalized_candidate:
            if abs(len(normalized_candidate) - len(normalized_reference)) <= 24:
                return False
        if _text_overlap_score(normalized_candidate, normalized_reference) >= 0.88:
            return False
    return True


def _strip_feed_metric_prefix(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"^\s*\d{1,2}:\d{2}\s*/\s*\d{1,2}:\d{2}\s*", "", text).strip()
    cleaned = re.sub(
        r"^(?:\d+(?:\.\d+)?[万亿wWkK]?\s+){2,3}\d+(?:\.\d+)?[万亿wWkK]?\s*",
        "",
        cleaned,
    ).strip()
    cleaned = re.sub(r"^听抖音\s*", "", cleaned).strip()
    return cleaned or None


def _summarize_text(text: str | None, limit: int = 180) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _build_feed_identity(
    video_url: str | None,
    creator_profile_url: str | None,
    creator_name: str | None,
    like_count_raw: str | None,
    comment_count_raw: str | None,
    favorite_count_raw: str | None,
    share_count_raw: str | None,
    text_summary: str | None,
) -> str | None:
    if normalized_video := _normalize_url(video_url):
        return normalized_video
    if creator_profile_url or creator_name:
        creator_anchor = "::".join(
            part
            for part in (
                _normalize_url(creator_profile_url),
                creator_name.strip() if creator_name else None,
                like_count_raw,
                comment_count_raw,
                favorite_count_raw,
                share_count_raw,
            )
            if part
        )
        if creator_anchor:
            return creator_anchor
    return text_summary


def _state_identity(state: dict | None) -> str | None:
    if not state:
        return None
    return _build_feed_identity(
        video_url=state.get("video_url"),
        creator_profile_url=state.get("creator_profile_url"),
        creator_name=state.get("creator_name"),
        like_count_raw=_extract_metric(state.get("active_text") or "", "点赞"),
        comment_count_raw=_extract_metric(state.get("active_text") or "", "评论"),
        favorite_count_raw=_extract_metric(state.get("active_text") or "", "收藏"),
        share_count_raw=_extract_metric(state.get("active_text") or "", "分享"),
        text_summary=_summarize_text(state.get("active_text")),
    )


def _feed_identity_changed(
    before_identity: str | None,
    after_identity: str | None,
    before_summary: str | None,
    after_summary: str | None,
) -> bool:
    if before_summary and after_summary and before_summary == after_summary:
        return False
    if before_identity and after_identity:
        return before_identity != after_identity
    if before_summary and after_summary:
        return before_summary != after_summary
    return False


def _normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip()
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    elif cleaned.startswith("/"):
        cleaned = urljoin(selectors.BASE_URL, cleaned)
    elif cleaned.startswith("www."):
        cleaned = f"https://{cleaned}"
    return cleaned.split("?")[0].rstrip("/")


def _looks_like_global_page_chrome(text: str | None) -> bool:
    if not text:
        return False
    chrome_hits = sum(1 for hint in selectors.GLOBAL_CHROME_HINTS if hint in text)
    footer_hits = sum(1 for hint in selectors.LEGAL_FOOTER_HINTS if hint in text)
    if footer_hits >= 1 and len(text) > 120:
        return True
    if chrome_hits >= 6 and len(text) > 80:
        return True
    return False

def _looks_like_commerce_feed_item(text: str | None) -> bool:
    """Detect shopping/product-card feed items.

    These items should be skipped because product cards can steal focus
    and make creator/video data unreliable.
    """
    if not text:
        return False

    haystack = re.sub(r"\s+", " ", text).strip()

    strong_hints = [
        "购物 |",
        "视频同款",
        "商品橱窗",
        "商品卡",
        "查看详情",
        "官方旗舰店",
        "旗舰店",
        "￥",
        "¥",
        "选择",
        "运费险",
        "7天无理由",
        "极速退款",
        "加入购物车",
        "立即购买",
        "领券",
    ]

    product_hints = [
        "素颜霜",
        "精华霜",
        "淡印霜",
        "护肤",
        "遮瑕",
        "粉底液",
        "痘印",
        "男士素颜霜",

        # 新增：服装/穿搭商品词
        "穿搭",
        "polo衫",
        "短袖",
        "短袖t恤",
        "t恤",
        "男生穿搭",
        "约会穿搭",
        "谁穿谁好看",
        "男装",
        "衣服",
        "上衣",
    ]

    # 非常明显的商品卡
    if "购物 |" in haystack or "视频同款" in haystack:
        return True

    # 店铺型账号，基本直接跳过
    if "官方旗舰店" in haystack or "旗舰店" in haystack:
        return True

    # 查看详情 + 商品词，通常是电商/商品内容
    if "查看详情" in haystack and any(hint in haystack for hint in product_hints):
        return True

    strong_hit_count = sum(1 for hint in strong_hints if hint in haystack)
    product_hit_count = sum(1 for hint in product_hints if hint in haystack)

    if ("￥" in haystack or "¥" in haystack) and strong_hit_count >= 2:
        return True

    if product_hit_count >= 1 and strong_hit_count >= 2:
        return True

    # 穿搭类商品内容：多个商品词同时出现，也跳过
    if product_hit_count >= 3 and any(token in haystack for token in ("穿搭", "短袖", "t恤", "polo衫")):
        return True

    return False

def _looks_like_live_feed_item(
    text: str | None,
    creator_profile_url: str | None = None,
    video_url: str | None = None,
) -> bool:
    if creator_profile_url and "/live" in creator_profile_url:
        return True
    if video_url and "/live" in video_url:
        return True
    if _looks_like_global_page_chrome(text):
        return False
    haystack = text or ""
    live_room_hits = sum(1 for hint in selectors.LIVE_ROOM_HINTS if hint in haystack)
    if live_room_hits >= 2:
        return True
    return any(hint in haystack for hint in ("直播中", "直播间"))


def _is_target_closed_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    return "target page, context or browser has been closed" in message or "targetclosederror" in message
