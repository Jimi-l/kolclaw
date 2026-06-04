from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from search_agent.artifacts import ArtifactManager
from search_agent.browser.page_utils import body_text, first_attribute, first_text, first_visible_locator, locator_text, page_contains_any_text
from search_agent.enums import BlockReason
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError
from search_agent.utils.normalize import normalize_currency_value

from . import selectors


@dataclass(slots=True)
class XingtuSearchCandidate:
    candidate_name: str | None
    candidate_follower_hint: str | None
    candidate_avatar_hint: str | None
    candidate_creator_type: str | None
    candidate_content_hint: str | None
    candidate_url: str | None
    candidate_row_selector: str | None = None
    candidate_row_index: int | None = None


@dataclass(slots=True)
class XingtuSearchOutcome:
    query: str
    result_kind: str
    candidates: list[XingtuSearchCandidate] = field(default_factory=list)


@dataclass(slots=True)
class XingtuDetailSnapshot:
    xingtu_id: str | None = None
    xingtu_profile_url: str | None = None
    xingtu_creator_type: str | None = None
    price_20s: float | None = None
    price_20_60s: float | None = None
    price_60s_plus: float | None = None
    price_insert_video: float | None = None
    price_custom_video: float | None = None
    price_douyin_image_text: float | None = None
    other_service_prices: dict[str, float] | None = None
    estimated_play: str | int | None = None
    sponsored_median_play: str | int | None = None
    natural_cpm: float | None = None
    cpe: float | None = None
    sponsored_completion_rate: str | float | None = None
    monthly_fan_growth_rate: str | float | None = None
    monthly_connected_user_fan_ratio: str | float | None = None
    monthly_deep_user_fan_ratio: str | float | None = None
    recent_15_curve_screenshot_path: str | None = None
    cooperate_brands: list[str] | None = None
    field_missing_list: list[str] = field(default_factory=list)


class XingtuPageAdapter:
    def __init__(self, page, artifacts: ArtifactManager, logger: logging.Logger):
        self.page = page
        self.artifacts = artifacts
        self.logger = logger
        self._search_page = page

    def open_homepage(self) -> None:
        self.open_creator_home()

    def open_creator_home(self) -> None:
        self.page.goto(selectors.CREATOR_BACKEND_HOME_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1_000)
        self.raise_for_blockers(page_name="xingtu_creator_home")


    def raise_for_blockers(self, page_name: str) -> None:
        if phrase := page_contains_any_text(self.page, selectors.CAPTCHA_HINTS):
            screenshot = self._capture(f"{page_name}_captcha")
            raise BlockingStateError(
                reason=BlockReason.CAPTCHA_BLOCKED,
                message=f"检测到星图验证码/人机验证提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please complete the captcha or slider verification in this Xingtu browser session and press Enter to retry.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.SESSION_EXPIRED_HINTS):
            screenshot = self._capture(f"{page_name}_session_expired")
            raise BlockingStateError(
                reason=BlockReason.SESSION_EXPIRED,
                message=f"检测到星图会话失效提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please log into Xingtu again in this browser session and press Enter to retry.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.PERMISSION_DENIED_HINTS):
            screenshot = self._capture(f"{page_name}_permission")
            raise BlockingStateError(
                reason=BlockReason.PERMISSION_DENIED,
                message=f"检测到星图权限不足提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please confirm whether this Xingtu account has creator-detail permission.",
            )
        if phrase := page_contains_any_text(self.page, selectors.ACCESS_RESTRICTED_HINTS):
            screenshot = self._capture(f"{page_name}_access")
            raise BlockingStateError(
                reason=BlockReason.XINGTU_ACCESS_RESTRICTED,
                message=f"检测到星图访问受限提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please confirm that this Xingtu account is allowed to access creator search and detail pages.",
            )
        if phrase := page_contains_any_text(self.page, selectors.QR_LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_qr_login")
            raise BlockingStateError(
                reason=BlockReason.QR_LOGIN_REQUIRED,
                message=f"当前星图页面需要扫码登录：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please scan the QR code and finish Xingtu login in this browser session. The workflow will continue automatically after /ad/creator/index loads.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.SMS_LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_sms_login")
            raise BlockingStateError(
                reason=BlockReason.SMS_LOGIN_REQUIRED,
                message=f"当前星图页面需要短信登录：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please complete the Xingtu SMS login flow in this browser session. The workflow will continue automatically after /ad/creator/index loads.",
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_login")
            raise BlockingStateError(
                reason=BlockReason.LOGIN_REQUIRED,
                message=f"当前星图页面需要登录：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please log into Xingtu in this browser session. The workflow will continue automatically after /ad/creator/index loads.",
                resumable=True,
            )

    def search(self, query: str) -> XingtuSearchOutcome:
        self._return_to_search_page()
        self.ensure_creator_search_page()
        self.raise_for_blockers(page_name="xingtu_search")
        search_input = first_visible_locator(self.page, selectors.SEARCH_INPUT_SELECTORS)
        if search_input is None:
            self._raise_search_input_missing()
        self._fill_search_input(search_input, query)
        self._click_search_button()
        self._wait_for_search_results_ready(query)
        self.raise_for_blockers(page_name="xingtu_search_results")

        if page_contains_any_text(self.page, selectors.UNREGISTERED_HINTS):
            return XingtuSearchOutcome(query=query, result_kind="unregistered")

        candidates = self._extract_candidates(limit=5)
        self.logger.debug(
            "xingtu search candidates extracted",
            extra={
                "query": query,
                "candidate_count": len(candidates),
                "candidates": [
                    {
                        "index": index,
                        "candidate_name": candidate.candidate_name,
                        "candidate_url": candidate.candidate_url,
                        "candidate_row_selector": candidate.candidate_row_selector,
                        "candidate_row_index": candidate.candidate_row_index,
                        "candidate_avatar_hint": candidate.candidate_avatar_hint,
                        "candidate_text": _debug_text_preview(candidate.candidate_content_hint),
                    }
                    for index, candidate in enumerate(candidates)
                ],
            },
        )
        if not candidates:
            return XingtuSearchOutcome(query=query, result_kind="not_found")
        return XingtuSearchOutcome(query=query, result_kind="matched_candidates", candidates=candidates)

    def ensure_creator_search_page(self) -> None:
        if self._is_creator_search_page():
            return
        self.logger.info(
            "xingtu navigating to creator home before search",
            extra={"current_url": self.page.url, "target_url": selectors.CREATOR_BACKEND_HOME_URL},
        )
        self.open_creator_home()

    def _is_creator_search_page(self) -> bool:
        return selectors.is_creator_backend_home_url(self.page.url)

    def _click_search_button(self) -> None:
        for selector in selectors.SEARCH_BUTTON_SELECTORS:
            try:
                locator = self.page.locator(selector).first
                if not locator.count() or not locator.is_visible(timeout=800):
                    continue
                locator.click()
                return
            except Exception:
                continue

    def _wait_for_search_results_ready(self, query: str, timeout_ms: int = 8_000) -> None:
        elapsed_ms = 0
        step_ms = 500
        while elapsed_ms < timeout_ms:
            if self._candidate_name_count() > 0:
                return
            page_text = body_text(self.page, timeout_ms=800)
            if page_contains_any_text(self.page, selectors.UNREGISTERED_HINTS):
                return
            if "\u627e\u5230" in page_text and "\u8fbe\u4eba" in page_text:
                return
            self.page.wait_for_timeout(step_ms)
            elapsed_ms += step_ms
        self.logger.debug(
            "xingtu search results readiness wait timed out",
            extra={"query": query, "url": self.page.url, "candidate_name_count": self._candidate_name_count()},
        )

    def _candidate_name_count(self) -> int:
        for selector in selectors.CANDIDATE_NAME_SELECTORS:
            try:
                count = self.page.locator(selector).count()
                if count:
                    return count
            except Exception:
                continue
        return 0

    def _fill_search_input(self, search_input, query: str) -> None:
        search_input.click()
        try:
            search_input.fill("")
        except Exception:
            pass
        search_input.fill(query)
        self.page.keyboard.press("Enter")

    def _raise_search_input_missing(self) -> None:
        screenshot = self._capture("xingtu_search_input")
        if self._is_public_landing_page():
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="当前仍停留在巨量星图公开营销页，尚未进入后台首页搜索页",
                page_name="xingtu_public_landing",
                screenshot_path=screenshot,
                required_user_action=(
                    "Please open Xingtu backend home manually, make sure the search box "
                    "'输入达人昵称、抖音号或星图ID' is visible, then press Enter to retry."
                ),
                resumable=True,
            )
        if phrase := page_contains_any_text(self.page, selectors.LOGIN_HINTS):
            raise BlockingStateError(
                reason=BlockReason.LOGIN_REQUIRED,
                message=f"当前星图页面尚未进入登录后的后台首页：{phrase}",
                page_name="xingtu_search",
                screenshot_path=screenshot,
                required_user_action=(
                    "Please finish Xingtu login and make sure the backend home search box "
                    "'输入达人昵称、抖音号或星图ID' is visible, then press Enter to retry."
                ),
                resumable=True,
            )
        raise PageStructureUncertainError(
            reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
            message="未能定位星图搜索框",
            page_name="xingtu_search",
            screenshot_path=screenshot,
            required_user_action=(
                "Please navigate this browser to Xingtu backend home, make sure the search box "
                "'输入达人昵称、抖音号或星图ID' is visible, then press Enter to retry."
            ),
            resumable=True,
        )

    def _is_public_landing_page(self) -> bool:
        if "redirect_uri=" in self.page.url and "/ad/creator" in self.page.url:
            return True
        page_text = body_text(self.page)
        self.logger.debug(
            "xingtu detail page text extracted",
            extra={"url": self.page.url, "text": _debug_text_preview(page_text)},
        )
        return "达人营销" in page_text and "好内容成就好生意" in page_text

    def open_candidate(self, candidate: XingtuSearchCandidate) -> None:
        self._search_page = self.page
        if self._click_candidate_avatar(candidate):
            self.page.wait_for_timeout(1_200)
            self.raise_for_blockers(page_name="xingtu_detail")
            return
        if not candidate.candidate_url:
            screenshot = self._capture("xingtu_candidate_missing_url")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="星图候选卡片缺少可用详情链接",
                page_name="xingtu_search_results",
                screenshot_path=screenshot,
                required_user_action="Please provide the selector or screenshot for the Xingtu result card detail link.",
            )
        self.page.goto(candidate.candidate_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1_200)
        self.raise_for_blockers(page_name="xingtu_detail")

    def _click_candidate_avatar(self, candidate: XingtuSearchCandidate) -> bool:
        if candidate.candidate_row_selector is None or candidate.candidate_row_index is None:
            return False
        try:
            source = self.page.locator(candidate.candidate_row_selector).nth(candidate.candidate_row_index)
            row = self._candidate_container_from_source(source)
            for selector in selectors.CANDIDATE_AVATAR_CLICK_SELECTORS:
                target = first_visible_locator(row, [selector], timeout_ms=800)
                if target is None:
                    continue
                before_url = self.page.url
                before_pages = self._context_pages()
                try:
                    if self._click_target_and_switch_to_popup(target):
                        self.logger.debug(
                            "xingtu candidate detail page opened in a new tab",
                            extra={
                                "selector": selector,
                                "candidate_name": candidate.candidate_name,
                                "before_url": before_url,
                                "after_url": self.page.url,
                            },
                        )
                        return True
                except Exception:
                    continue
                if self._switch_to_new_detail_page(before_pages):
                    self.logger.debug(
                        "xingtu candidate detail page opened in a new tab",
                        extra={
                            "selector": selector,
                            "candidate_name": candidate.candidate_name,
                            "before_url": before_url,
                            "after_url": self.page.url,
                        },
                    )
                    return True
                if self._candidate_click_reached_detail_page(before_url):
                    return True
                self.logger.debug(
                    "xingtu candidate click did not open detail page",
                    extra={
                        "selector": selector,
                        "candidate_name": candidate.candidate_name,
                        "before_url": before_url,
                        "after_url": self.page.url,
                    },
                )
            return False
        except Exception:
            return False

    def _click_target_and_switch_to_popup(self, target, timeout_ms: int = 6_000) -> bool:
        try:
            target.scroll_into_view_if_needed(timeout=1_000)
        except Exception:
            pass
        try:
            with self.page.expect_popup(timeout=timeout_ms) as popup_info:
                target.click()
            popup = popup_info.value
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            if not self._is_candidate_detail_url(popup.url):
                return False
            self._search_page = self.page
            self.page = popup
            try:
                self.page.bring_to_front()
            except Exception:
                pass
            return True
        except Exception:
            try:
                target.click()
            except Exception:
                return False
            return False

    def _context_pages(self) -> list:
        try:
            context = getattr(self.page, "context", None)
            return list(context.pages) if context is not None else []
        except Exception:
            return []

    def _switch_to_new_detail_page(self, before_pages: list, timeout_ms: int = 8_000) -> bool:
        elapsed_ms = 0
        step_ms = 500
        before_ids = {id(page) for page in before_pages}
        while elapsed_ms < timeout_ms:
            try:
                context = getattr(self.page, "context", None)
                if context is None:
                    return False
                candidate_pages = [page for page in context.pages if id(page) not in before_ids]
                for page in reversed(candidate_pages):
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=1_000)
                    except Exception:
                        pass
                    if self._is_candidate_detail_url(page.url):
                        self._search_page = self.page
                        self.page = page
                        try:
                            self.page.bring_to_front()
                        except Exception:
                            pass
                        return True
            except Exception:
                return False
            self.page.wait_for_timeout(step_ms)
            elapsed_ms += step_ms
        return False

    def _candidate_click_reached_detail_page(self, before_url: str) -> bool:
        if self.page.url == before_url:
            return False
        if self._is_creator_search_page():
            return False
        return self._is_candidate_detail_url(self.page.url)

    def _is_candidate_detail_url(self, url: str) -> bool:
        return "/ad/creator/author-homepage/" in url or ("/ad/creator/" in url and "/ad/creator/market" not in url)

    def close_current_detail_page(self) -> None:
        if not self._is_candidate_detail_url(self.page.url):
            return
        detail_page = self.page
        self._return_to_search_page()
        try:
            if detail_page is not self.page and not detail_page.is_closed():
                detail_page.close()
        except Exception:
            self.logger.debug("xingtu detail page close failed", exc_info=True)

    def _return_to_search_page(self) -> None:
        try:
            if self.page is self._search_page:
                return
            if self._search_page is not None and not self._search_page.is_closed():
                self.page = self._search_page
                try:
                    self.page.bring_to_front()
                except Exception:
                    pass
        except Exception:
            pass

    def _candidate_container_from_source(self, source):
        try:
            container = source.locator("xpath=ancestor::*[.//*[contains(@class, 'author-info-avatar')]][1]")
            if container.count():
                return container.first
        except Exception:
            pass
        return source

    def extract_details(self, creator_slug: str) -> XingtuDetailSnapshot:
        if first_visible_locator(self.page, selectors.DETAIL_READY_SELECTORS) is None:
            screenshot = self._capture("xingtu_detail_structure")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="未能定位星图达人详情页主容器",
                page_name="xingtu_detail",
                screenshot_path=screenshot,
                required_user_action="Please provide a screenshot or DOM snapshot of the Xingtu creator detail page.",
        )

        self._wait_for_detail_content_ready()
        page_text = body_text(self.page)
        self.logger.debug(
            "xingtu detail page text extracted",
            extra={"url": self.page.url, "text": _debug_text_preview(page_text)},
        )
        snapshot = XingtuDetailSnapshot(
            xingtu_id=_extract_xingtu_id(self.page.url, page_text),
            xingtu_profile_url=self.page.url,
            xingtu_creator_type=_extract_labeled_text(page_text, ("达人类型", "创作者类型")),
            price_20s=normalize_currency_value(_extract_labeled_text(page_text, ("20s", "1-20s", "20秒"))),
            price_20_60s=normalize_currency_value(_extract_labeled_text(page_text, ("20-60s", "21-60s", "20-60秒"))),
            price_60s_plus=normalize_currency_value(_extract_labeled_text(page_text, ("60s+", "60秒+", "60s以上"))),
            estimated_play=_extract_labeled_text(page_text, ("预估播放量", "预估播放")),
            sponsored_median_play=_extract_labeled_text(page_text, ("商单播放量中位数", "商单播放中位数")),
            natural_cpm=normalize_currency_value(_extract_labeled_text(page_text, ("自然量CPM", "CPM"))),
            cpe=normalize_currency_value(_extract_labeled_text(page_text, ("CPE",))),
            sponsored_completion_rate=_extract_labeled_text(page_text, ("商单完播率",)),
            monthly_fan_growth_rate=_extract_labeled_text(page_text, ("月涨粉率",)),
            monthly_connected_user_fan_ratio=_extract_labeled_text(page_text, ("月连接用户粉丝比",)),
            monthly_deep_user_fan_ratio=_extract_labeled_text(page_text, ("月深度用户粉丝比",)),
            cooperate_brands=_extract_brands(page_text),
        )
        _fill_author_homepage_fields(snapshot, page_text)
        curve_locator = first_visible_locator(self.page, selectors.RECENT_CURVE_SELECTORS)
        if curve_locator is not None:
            path = self.artifacts.screenshot_path(f"{creator_slug}_recent15_curve")
            try:
                curve_locator.screenshot(path=str(path))
                snapshot.recent_15_curve_screenshot_path = str(path)
            except Exception:
                snapshot.field_missing_list.append("recent_15_curve_screenshot_path")
        else:
            snapshot.field_missing_list.append("recent_15_curve_screenshot_path")

        for field_name in (
            "xingtu_id",
            "xingtu_creator_type",
            "price_20s",
            "price_20_60s",
            "price_60s_plus",
            "estimated_play",
            "sponsored_median_play",
            "natural_cpm",
            "cpe",
            "sponsored_completion_rate",
            "monthly_fan_growth_rate",
            "monthly_connected_user_fan_ratio",
            "monthly_deep_user_fan_ratio",
        ):
            if getattr(snapshot, field_name) in {None, ""} and field_name not in snapshot.field_missing_list:
                snapshot.field_missing_list.append(field_name)
        return snapshot

    def _wait_for_detail_content_ready(self, timeout_ms: int = 10_000) -> None:
        elapsed_ms = 0
        step_ms = 500
        stable_hits = 0
        last_length = -1
        last_preview = None
        while elapsed_ms < timeout_ms:
            page_text = body_text(self.page, timeout_ms=1_000)
            current_length = len(page_text)
            last_preview = _debug_text_preview(page_text)
            has_identity = self._is_candidate_detail_url(self.page.url) and (
                "ID:" in page_text or "\u661f\u56feID" in page_text
            )
            has_business_content = any(
                marker in page_text
                for marker in (
                    "\u8fbe\u4eba\u670d\u52a1\u62a5\u4ef7",
                    "\u5546\u4e1a\u80fd\u529b",
                    "\u64ad\u653e\u91cf\u4e2d\u4f4d\u6570",
                    "CPM",
                    "CPC",
                )
            )
            has_price_content = any(
                marker in page_text
                for marker in (
                    "1-20s",
                    "0-20s",
                    "21-60s",
                    "20-60s",
                    "60s",
                    "\uffe5",
                    "\u00a5",
                )
            )
            if current_length == last_length and has_identity and has_business_content:
                stable_hits += 1
            else:
                stable_hits = 0
            if stable_hits >= 2 and (has_price_content or has_business_content):
                return
            last_length = current_length
            self.page.wait_for_timeout(step_ms)
            elapsed_ms += step_ms
        self.logger.debug(
            "xingtu detail content readiness wait timed out",
            extra={"url": self.page.url, "text": last_preview},
        )

    def _extract_candidates(self, limit: int) -> list[XingtuSearchCandidate]:
        candidates: list[XingtuSearchCandidate] = []
        for selector in selectors.RESULT_CARD_SELECTORS:
            try:
                locator = self.page.locator(selector)
                count = locator.count()
                self.logger.debug(
                    "xingtu candidate selector scanned",
                    extra={"selector": selector, "count": count},
                )
                if not count:
                    continue
                for index in range(count):
                    item = locator.nth(index)
                    text = locator_text(item) or ""
                    candidate_name = _extract_candidate_name(item, text)
                    if not candidate_name and selector in selectors.CANDIDATE_NAME_SELECTORS:
                        candidate_name = _clean_candidate_name(text)
                    self.logger.debug(
                        "xingtu candidate row read",
                        extra={
                            "selector": selector,
                            "row_index": index,
                            "candidate_name": candidate_name,
                            "raw_text": _debug_text_preview(text),
                        },
                    )
                    if not candidate_name:
                        continue
                    href = item.get_attribute("href") or first_attribute(item, selectors.CANDIDATE_URL_SELECTORS, "href")
                    if href and href.startswith("/"):
                        href = f"https://www.xingtu.cn{href}"
                    avatar = None
                    try:
                        image = item.locator("img").first
                        if image.count():
                            avatar = image.get_attribute("src")
                    except Exception:
                        avatar = None
                    candidates.append(
                        XingtuSearchCandidate(
                            candidate_name=candidate_name,
                            candidate_follower_hint=first_text(item, selectors.CANDIDATE_FOLLOWER_SELECTORS) or _extract_labeled_text(text, ("粉丝",)),
                            candidate_avatar_hint=avatar,
                            candidate_creator_type=first_text(item, selectors.CANDIDATE_TYPE_SELECTORS),
                            candidate_content_hint=text,
                            candidate_url=href,
                            candidate_row_selector=selector,
                            candidate_row_index=index,
                        )
                    )
                    self.logger.debug(
                        "xingtu candidate accepted",
                        extra={
                            "selector": selector,
                            "row_index": index,
                            "candidate_name": candidate_name,
                            "candidate_url": href,
                            "candidate_avatar_hint": avatar,
                            "raw_text": _debug_text_preview(text),
                        },
                    )
                    if len(candidates) >= limit:
                        break
                if candidates:
                    return candidates
            except Exception:
                continue
        return candidates

    def _capture(self, label: str) -> str:
        path = self.artifacts.screenshot_path(label)
        self.page.screenshot(path=str(path), full_page=True)
        return str(path)


def _extract_xingtu_id(url: str, page_text: str) -> str | None:
    homepage_match = re.search(r"/author-homepage/[^/]+/([^/?#]+)", url)
    if homepage_match:
        return homepage_match.group(1)
    url_match = re.search(r"/creator/([^/?#]+)", url)
    if url_match:
        return url_match.group(1)
    labeled_match = re.search(r"星图ID\s*[:：]?\s*([A-Za-z0-9_-]+)", page_text)
    if labeled_match:
        return labeled_match.group(1)
    text_match = re.search(r"(MS4w[\w-]+)", page_text)
    return text_match.group(1) if text_match else None


def _extract_service_prices(page_text: str) -> dict[str, float | None]:
    return {
        "price_20s": _extract_price_after_label(
            page_text,
            (
                "1-20s视频",
                "0-20s视频",
                "1-20s",
                "0-20s",
                "\u0031-\u0032\u0030s\u89c6\u9891",
                "\u0030-\u0032\u0030s\u89c6\u9891",
            ),
        ),
        "price_20_60s": _extract_price_after_label(
            page_text,
            (
                "21-60s视频",
                "20-60s视频",
                "21-60s",
                "20-60s",
                "\u0032\u0031-\u0036\u0030s\u89c6\u9891",
                "\u0032\u0030-\u0036\u0030s\u89c6\u9891",
            ),
        ),
        "price_60s_plus": _extract_price_after_label(
            page_text,
            (
                "60s以上视频",
                "60s以上",
                "60s+视频",
                "60s+",
                "\u0036\u0030s\u4ee5\u4e0a\u89c6\u9891",
            ),
        ),
    }


def _fill_author_homepage_fields(snapshot: XingtuDetailSnapshot, page_text: str) -> None:
    service_prices = _extract_service_prices(page_text)
    if snapshot.price_20s is None:
        snapshot.price_20s = service_prices.get("price_20s")
    if snapshot.price_20_60s is None:
        snapshot.price_20_60s = service_prices.get("price_20_60s")
    if snapshot.price_60s_plus is None:
        snapshot.price_60s_plus = service_prices.get("price_60s_plus")
    if snapshot.price_insert_video is None:
        snapshot.price_insert_video = service_prices.get("price_insert_video")
    if snapshot.price_custom_video is None:
        snapshot.price_custom_video = service_prices.get("price_custom_video")
    if snapshot.price_douyin_image_text is None:
        snapshot.price_douyin_image_text = service_prices.get("price_douyin_image_text")
    if snapshot.other_service_prices is None:
        snapshot.other_service_prices = service_prices.get("other_service_prices")
    if snapshot.xingtu_creator_type is None:
        snapshot.xingtu_creator_type = _extract_labeled_text(page_text, ("达人类型", "创作者类型"))
    if snapshot.estimated_play is None:
        snapshot.estimated_play = _extract_labeled_text(page_text, ("预期播放量",))
    if snapshot.sponsored_median_play is None:
        snapshot.sponsored_median_play = _extract_labeled_text(page_text, ("播放量中位数", "商单播放量中位数"))
    if snapshot.natural_cpm is None:
        snapshot.natural_cpm = normalize_currency_value(_extract_labeled_text(page_text, ("预期CPM", "自然量CPM")))
    if snapshot.cpe is None:
        snapshot.cpe = normalize_currency_value(_extract_labeled_text(page_text, ("CPE", "CPC")))
    if snapshot.sponsored_completion_rate is None:
        snapshot.sponsored_completion_rate = _extract_labeled_text(page_text, ("完播率",))
    if snapshot.monthly_connected_user_fan_ratio is None:
        snapshot.monthly_connected_user_fan_ratio = _extract_labeled_text(page_text, ("月连接用户数",))
    if snapshot.monthly_deep_user_fan_ratio is None:
        snapshot.monthly_deep_user_fan_ratio = _extract_labeled_text(page_text, ("月深度用户数",))


def _extract_labeled_text(page_text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}[:：]?\s*([^\n]+)"
        match = re.search(pattern, page_text)
        if match:
            value = match.group(1).strip()
            if value:
                return value.split("  ")[0].strip()
    return None


def _extract_service_prices(page_text: str) -> dict[str, float | None]:
    return {
        "price_20s": _extract_price_after_label(
            page_text,
            (
                "1-20s视频",
                "0-20s视频",
                "1-20s",
                "0-20s",
                "\u0031-\u0032\u0030s\u89c6\u9891",
                "\u0030-\u0032\u0030s\u89c6\u9891",
            ),
        ),
        "price_20_60s": _extract_price_after_label(
            page_text,
            (
                "21-60s视频",
                "20-60s视频",
                "21-60s",
                "20-60s",
                "\u0032\u0031-\u0036\u0030s\u89c6\u9891",
                "\u0032\u0030-\u0036\u0030s\u89c6\u9891",
            ),
        ),
        "price_60s_plus": _extract_price_after_label(
            page_text,
            (
                "60s以上视频",
                "60s以上",
                "60s+视频",
                "60s+",
                "\u0036\u0030s\u4ee5\u4e0a\u89c6\u9891",
            ),
        ),
    }


def _extract_price_after_label(page_text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        patterns = (
            rf"{re.escape(label)}\s*[:：]?\s*([￥¥]?\s*[\d,]+(?:\.\d+)?\s*(?:万|w|k|元)?)",
            rf"([￥¥]?\s*[\d,]+(?:\.\d+)?\s*(?:万|w|k|元)?)\s*{re.escape(label)}",
        )
        for pattern in patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if not match:
                continue
            price = normalize_currency_value(match.group(1))
            if price is not None:
                return price
    return None


def _fill_author_homepage_fields(snapshot: XingtuDetailSnapshot, page_text: str) -> None:
    service_prices = _extract_service_prices(page_text)
    if snapshot.price_20s is None:
        snapshot.price_20s = service_prices.get("price_20s")
    if snapshot.price_20_60s is None:
        snapshot.price_20_60s = service_prices.get("price_20_60s")
    if snapshot.price_60s_plus is None:
        snapshot.price_60s_plus = service_prices.get("price_60s_plus")
    if snapshot.price_insert_video is None:
        snapshot.price_insert_video = _extract_price_after_label(page_text, ("植入视频", "\u690d\u5165\u89c6\u9891"))
    if snapshot.price_custom_video is None:
        snapshot.price_custom_video = _extract_price_after_label(page_text, ("定制视频", "\u5b9a\u5236\u89c6\u9891"))
    if snapshot.price_douyin_image_text is None:
        snapshot.price_douyin_image_text = _extract_price_after_label(page_text, ("抖音图文", "\u6296\u97f3\u56fe\u6587"))
    if snapshot.other_service_prices is None:
        snapshot.other_service_prices = _extract_other_service_prices(page_text)
    if snapshot.xingtu_creator_type is None:
        snapshot.xingtu_creator_type = _extract_labeled_text(page_text, ("达人类型", "\u8fbe\u4eba\u7c7b\u578b", "创作者类型", "\u521b\u4f5c\u8005\u7c7b\u578b"))
    if snapshot.estimated_play is None:
        snapshot.estimated_play = _extract_labeled_text(page_text, ("预期播放量", "\u9884\u671f\u64ad\u653e\u91cf"))
    if snapshot.sponsored_median_play is None:
        snapshot.sponsored_median_play = _extract_labeled_text(page_text, ("播放量中位数", "\u64ad\u653e\u91cf\u4e2d\u4f4d\u6570", "商单播放量中位数", "\u5546\u5355\u64ad\u653e\u91cf\u4e2d\u4f4d\u6570"))
    if snapshot.natural_cpm is None:
        snapshot.natural_cpm = normalize_currency_value(_extract_labeled_text(page_text, ("预期CPM", "\u9884\u671fCPM", "自然量CPM", "\u81ea\u7136\u91cfCPM")))
    if snapshot.cpe is None:
        snapshot.cpe = normalize_currency_value(_extract_labeled_text(page_text, ("CPE", "CPC")))
    if snapshot.sponsored_completion_rate is None:
        snapshot.sponsored_completion_rate = _extract_labeled_text(page_text, ("完播率", "\u5b8c\u64ad\u7387"))
    if snapshot.monthly_connected_user_fan_ratio is None:
        snapshot.monthly_connected_user_fan_ratio = _extract_labeled_text(page_text, ("月连接用户数", "\u6708\u8fde\u63a5\u7528\u6237\u6570"))
    if snapshot.monthly_deep_user_fan_ratio is None:
        snapshot.monthly_deep_user_fan_ratio = _extract_labeled_text(page_text, ("月深度用户数", "\u6708\u6df1\u5ea6\u7528\u6237\u6570"))


def _extract_other_service_prices(page_text: str) -> dict[str, float] | None:
    known_labels = {
        "1-20s视频",
        "0-20s视频",
        "21-60s视频",
        "20-60s视频",
        "60s以上视频",
        "植入视频",
        "定制视频",
        "抖音图文",
    }
    matches = re.findall(
        r"([￥¥]\s*[\d,]+(?:\.\d+)?\s*(?:万|w|k|元)?)\s*([^￥¥\s][^￥¥]*?)(?=\s+下单|\s+[￥¥]|$)",
        page_text,
    )
    prices: dict[str, float] = {}
    for raw_price, raw_label in matches:
        label = re.sub(r"\s+", " ", raw_label).strip()
        if not label or label in known_labels:
            continue
        price = normalize_currency_value(raw_price)
        if price is not None:
            prices[label] = price
    return prices or None


def _extract_candidate_name(item, item_text: str) -> str | None:
    selector_name = first_text(item, selectors.CANDIDATE_NAME_SELECTORS)
    if selector_name:
        return _clean_candidate_name(selector_name)
    return None


def _extract_labeled_text(page_text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]?\s*([^\n]+)"
        match = re.search(pattern, page_text)
        if not match:
            continue
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        if value:
            return value
    return None


def _clean_candidate_name(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return None
    text = re.split(r"\s+(男|女|北京|上海|广州|深圳|杭州|成都|抖音|星图|繁星全企|抖音精选)\b", text, maxsplit=1)[0].strip()
    return text or None


def _debug_text_preview(value: str | None, limit: int = 500) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _looks_like_result_header(value: str) -> bool:
    normalized = value.strip()
    return normalized in {
        "达人信息",
        "代表视频",
        "达人类型",
        "内容主题",
        "连接用户数",
        "粉丝数",
        "预期CPM",
        "预期播放量",
        "互动率",
        "21-60s报价",
        "操作",
    }


def _extract_service_prices(page_text: str) -> dict[str, float | None]:
    return {
        "price_20s": _extract_price_after_label(
            page_text,
            (
                "1-20s\u89c6\u9891",
                "0-20s\u89c6\u9891",
                "1-20s",
                "0-20s",
            ),
        ),
        "price_20_60s": _extract_price_after_label(
            page_text,
            (
                "21-60s\u89c6\u9891",
                "20-60s\u89c6\u9891",
                "21-60s",
                "20-60s",
            ),
        ),
        "price_60s_plus": _extract_price_after_label(
            page_text,
            (
                "60s\u4ee5\u4e0a\u89c6\u9891",
                "60s\u4ee5\u4e0a",
                "60s+\u89c6\u9891",
                "60s+",
            ),
        ),
    }


def _extract_price_after_label(page_text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        patterns = (
            rf"{re.escape(label)}\s*[:\uff1a]?\s*([\uffe5\u00a5]?\s*[\d,]+(?:\.\d+)?\s*(?:\u4e07|w|k|\u5143)?)",
            rf"([\uffe5\u00a5]?\s*[\d,]+(?:\.\d+)?\s*(?:\u4e07|w|k|\u5143)?)\s*{re.escape(label)}",
        )
        for pattern in patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if not match:
                continue
            price = normalize_currency_value(match.group(1))
            if price is not None:
                return price
    return None


def _extract_other_service_prices(page_text: str) -> dict[str, float] | None:
    known_labels = {
        "1-20s\u89c6\u9891",
        "0-20s\u89c6\u9891",
        "21-60s\u89c6\u9891",
        "20-60s\u89c6\u9891",
        "60s\u4ee5\u4e0a\u89c6\u9891",
        "\u690d\u5165\u89c6\u9891",
        "\u5b9a\u5236\u89c6\u9891",
        "\u6296\u97f3\u56fe\u6587",
    }
    matches = re.findall(
        r"([\uffe5\u00a5]\s*[\d,]+(?:\.\d+)?\s*(?:\u4e07|w|k|\u5143)?)\s*([^\uffe5\u00a5\s][^\uffe5\u00a5]*?)(?=\s+\u4e0b\u5355|\s+[\uffe5\u00a5]|$)",
        page_text,
    )
    prices: dict[str, float] = {}
    for raw_price, raw_label in matches:
        label = re.sub(r"\s+", " ", raw_label).strip()
        if not label or label in known_labels:
            continue
        price = normalize_currency_value(raw_price)
        if price is not None:
            prices[label] = price
    return prices or None


def _extract_brands(page_text: str) -> list[str] | None:
    match = re.search(r"合作客户[:：]?\s*([^\n]+)", page_text)
    if not match:
        return None
    raw = match.group(1)
    parts = [item.strip() for item in re.split(r"[、,，/]", raw) if item.strip()]
    return parts or None
