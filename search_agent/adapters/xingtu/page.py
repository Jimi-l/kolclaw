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

    def open_homepage(self) -> None:
        self.page.goto(selectors.BASE_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1_000)
        self.raise_for_blockers(page_name="xingtu_home")

    def raise_for_blockers(self, page_name: str) -> None:
        if phrase := page_contains_any_text(self.page, selectors.CAPTCHA_HINTS):
            screenshot = self._capture(f"{page_name}_captcha")
            raise BlockingStateError(
                reason=BlockReason.CAPTCHA_BLOCKED,
                message=f"检测到星图验证码/人机验证提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please complete the captcha or slider verification in this Xingtu browser session and rerun.",
            )
        if phrase := page_contains_any_text(self.page, selectors.SESSION_EXPIRED_HINTS):
            screenshot = self._capture(f"{page_name}_session_expired")
            raise BlockingStateError(
                reason=BlockReason.SESSION_EXPIRED,
                message=f"检测到星图会话失效提示：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please log into Xingtu again in this browser session and tell me when it is done.",
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
                required_user_action="Please scan the QR code and finish Xingtu login in this browser session.",
            )
        if phrase := page_contains_any_text(self.page, selectors.SMS_LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_sms_login")
            raise BlockingStateError(
                reason=BlockReason.SMS_LOGIN_REQUIRED,
                message=f"当前星图页面需要短信登录：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please complete the Xingtu SMS login flow in this browser session.",
            )
        if phrase := page_contains_any_text(self.page, selectors.LOGIN_HINTS):
            screenshot = self._capture(f"{page_name}_login")
            raise BlockingStateError(
                reason=BlockReason.LOGIN_REQUIRED,
                message=f"当前星图页面需要登录：{phrase}",
                page_name=page_name,
                screenshot_path=screenshot,
                required_user_action="Please log into Xingtu in this browser session and tell me when it is done.",
            )

    def search(self, query: str) -> XingtuSearchOutcome:
        self.raise_for_blockers(page_name="xingtu_search")
        search_input = first_visible_locator(self.page, selectors.SEARCH_INPUT_SELECTORS)
        if search_input is None:
            screenshot = self._capture("xingtu_search_input")
            raise PageStructureUncertainError(
                reason=BlockReason.PAGE_STRUCTURE_UNCERTAINTY,
                message="未能定位星图搜索框",
                page_name="xingtu_search",
                screenshot_path=screenshot,
                required_user_action="Please provide a screenshot or DOM snapshot of the Xingtu search page.",
            )
        search_input.click()
        search_input.fill(query)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(1_500)
        self.raise_for_blockers(page_name="xingtu_search_results")

        if page_contains_any_text(self.page, selectors.UNREGISTERED_HINTS):
            return XingtuSearchOutcome(query=query, result_kind="unregistered")

        candidates = self._extract_candidates(limit=5)
        if not candidates:
            return XingtuSearchOutcome(query=query, result_kind="not_found")
        return XingtuSearchOutcome(query=query, result_kind="matched_candidates", candidates=candidates)

    def open_candidate(self, candidate: XingtuSearchCandidate) -> None:
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

        page_text = body_text(self.page)
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

    def _extract_candidates(self, limit: int) -> list[XingtuSearchCandidate]:
        candidates: list[XingtuSearchCandidate] = []
        for selector in selectors.RESULT_CARD_SELECTORS:
            try:
                locator = self.page.locator(selector)
                count = locator.count()
                if not count:
                    continue
                for index in range(min(count, limit)):
                    item = locator.nth(index)
                    text = locator_text(item) or ""
                    href = item.get_attribute("href")
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
                            candidate_name=first_text(item, selectors.CANDIDATE_NAME_SELECTORS) or text.splitlines()[0].strip() if text else None,
                            candidate_follower_hint=first_text(item, selectors.CANDIDATE_FOLLOWER_SELECTORS) or _extract_labeled_text(text, ("粉丝",)),
                            candidate_avatar_hint=avatar,
                            candidate_creator_type=first_text(item, selectors.CANDIDATE_TYPE_SELECTORS),
                            candidate_content_hint=text,
                            candidate_url=href,
                        )
                    )
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
    url_match = re.search(r"/creator/([^/?#]+)", url)
    if url_match:
        return url_match.group(1)
    text_match = re.search(r"(MS4w[\w-]+)", page_text)
    return text_match.group(1) if text_match else None


def _extract_labeled_text(page_text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}[:：]?\s*([^\n]+)"
        match = re.search(pattern, page_text)
        if match:
            value = match.group(1).strip()
            if value:
                return value.split("  ")[0].strip()
    return None


def _extract_brands(page_text: str) -> list[str] | None:
    match = re.search(r"合作客户[:：]?\s*([^\n]+)", page_text)
    if not match:
        return None
    raw = match.group(1)
    parts = [item.strip() for item in re.split(r"[、,，/]", raw) if item.strip()]
    return parts or None
