from __future__ import annotations

import asyncio
import re
from typing import Any, TYPE_CHECKING

from app.schemas.xingtu import XingtuCreatorDetail, XingtuCreatorRow, XingtuFilterConfig
from app.services.xingtu_selectors import (
    OPTIONAL_POPUP_CLOSE_SELECTORS,
    XingtuDetailSelectors,
    XingtuFilterSelectors,
    XingtuNavigationSelectors,
    XingtuResultSelectors,
)

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page
else:
    Locator = Any
    Page = Any


async def open_homepage(page: Page, base_url: str | None = None) -> None:
    """Open the authenticated Xingtu homepage."""

    await page.goto(base_url or XingtuNavigationSelectors.WORKSPACE_URL, wait_until="domcontentloaded")
    await _best_effort_network_idle(page)
    await dismiss_non_blocking_popups(page)
    await page.locator(XingtuNavigationSelectors.WORKSPACE_SHELL).first.wait_for(state="visible")


async def select_workspace_account(page: Page, account_name: str) -> None:
    """Select an account/workspace card when the homepage requires an explicit entry click."""

    content_root = page.locator(XingtuNavigationSelectors.CONTENT_ROOT).first
    account_card = content_root.locator(XingtuNavigationSelectors.WORKSPACE_ACCOUNT_CARD).filter(
        has_text=_account_name_regex(account_name)
    )

    candidate = await _pick_smallest_visible_locator(account_card)
    if candidate is not None:
        await candidate.click()
    else:
        generic_div_match = page.locator("div").filter(has_text=_account_name_regex(account_name))
        candidate = await _pick_smallest_visible_locator(generic_div_match)
        if candidate is not None:
            await candidate.click()
        else:
            await content_root.get_by_text(account_name, exact=True).click()

    await _best_effort_network_idle(page)
    await dismiss_non_blocking_popups(page)


async def open_workspace(page: Page, account_name: str | None = None, base_url: str | None = None) -> None:
    """Open Xingtu from an already authenticated browser context.

    If the account picker is shown after login, pass `account_name` so the
    workflow can enter the correct workspace before navigating deeper.
    """

    await open_homepage(page, base_url=base_url)
    if account_name:
        await select_workspace_account(page, account_name)


async def open_creator_search(page: Page) -> None:
    """Navigate from the workspace shell to the creator-search surface."""

    await dismiss_non_blocking_popups(page)

    nav_root = page.locator(XingtuNavigationSelectors.CONTENT_ROOT).first
    nav_link = page.get_by_role("link", name=XingtuNavigationSelectors.CREATOR_SEARCH_ENTRY_TEXT)
    if await nav_link.count():
        await nav_link.first.click()
    elif await nav_root.get_by_role("link", name=XingtuNavigationSelectors.CREATOR_SEARCH_ENTRY_TEXT).count():
        await nav_root.get_by_role("link", name=XingtuNavigationSelectors.CREATOR_SEARCH_ENTRY_TEXT).first.click()
    else:
        await page.locator(XingtuNavigationSelectors.CREATOR_SEARCH_ENTRY_FALLBACK).first.click()

    await _best_effort_network_idle(page)
    await dismiss_non_blocking_popups(page)


async def apply_filters(page: Page, filter_config: XingtuFilterConfig) -> None:
    """Apply a normalized filter config to the current Xingtu creator-search page."""

    if filter_config.keyword:
        await _fill_if_visible(page.locator(XingtuFilterSelectors.KEYWORD_INPUT).first, filter_config.keyword)

    for filter_name, values in filter_config.named_filters.items():
        await _apply_dropdown_filter(page, filter_name, values)

    await _apply_tag_filters(page, "达人类型", filter_config.creator_types)
    await _apply_tag_filters(page, "内容分类", filter_config.content_categories)
    await _apply_tag_filters(page, "城市", filter_config.cities)
    await _apply_tag_filters(page, "更多标签", filter_config.extra_tags)

    await _apply_range_filter(page, "报价", filter_config.price_min, filter_config.price_max)
    await _apply_range_filter(page, "粉丝", filter_config.fans_min, filter_config.fans_max)
    await _apply_range_filter(page, "女性占比", filter_config.female_ratio_min, filter_config.female_ratio_max)

    if filter_config.sort_by:
        await _apply_sort(page, filter_config.sort_by)

    await _click_if_visible(page.locator(XingtuFilterSelectors.APPLY_BUTTON).first)
    await _best_effort_network_idle(page)
    await dismiss_non_blocking_popups(page)


async def collect_current_page_rows(page: Page, row_limit: int | None = None) -> list[XingtuCreatorRow]:
    """Collect normalized row payloads from the current results table."""

    rows = await _resolve_result_items(page)
    count = await rows.count()
    limit = min(count, row_limit) if row_limit is not None else count

    results: list[XingtuCreatorRow] = []
    for index in range(limit):
        row = rows.nth(index)
        columns = await _collect_all_texts(row.locator(XingtuResultSelectors.ROW_COLUMNS))
        raw_text = await _safe_inner_text(row)
        name_link = row.locator(XingtuResultSelectors.ROW_NAME).first
        creator_name = await _safe_inner_text(name_link)
        xingtu_link = await _safe_attribute(name_link, "href")
        normalized_name = creator_name or raw_text

        results.append(
            XingtuCreatorRow(
                row_index=index,
                creator_name=normalized_name,
                creator_id=_extract_creator_id(xingtu_link or normalized_name or raw_text),
                xingtu_link=xingtu_link,
                creator_types=_split_tags(columns[1] if len(columns) > 1 else None),
                city=_pick_text_like(columns, ("上海", "北京", "广州", "深圳", "杭州", "成都")),
                fans_count=_first_number_like(columns, ("粉丝", "万", "亿")),
                female_ratio=_first_ratio_like(columns, ("%", "占比")),
                quoted_price=_first_currency_like(columns),
                median_commercial_play=_first_number_like(columns, ("播放", "w", "万")),
                natural_cpm=_first_decimal_like(columns, ("cpm", "CPM")),
                raw_columns=columns,
                raw_text=raw_text,
            )
        )

    return results


async def open_creator_detail(page: Page, row_index: int) -> Page:
    """Open a creator detail page from a results row.

    Xingtu may open detail in the same tab or a new tab depending on account state
    and UI variant. This helper supports both patterns.
    """

    rows = await _resolve_result_items(page)
    row = rows.nth(row_index)
    await row.scroll_into_view_if_needed()
    await dismiss_non_blocking_popups(page)

    link = row.locator(XingtuResultSelectors.ROW_NAME).first
    click_target = link if await link.count() else row
    detail_page = await _click_and_resolve_detail_page(page, click_target)

    await detail_page.wait_for_load_state("domcontentloaded")
    await _best_effort_network_idle(detail_page)
    await dismiss_non_blocking_popups(detail_page)
    await detail_page.locator(XingtuDetailSelectors.PAGE_READY).first.wait_for(state="visible")
    return detail_page


async def collect_creator_detail(page: Page) -> XingtuCreatorDetail:
    """Collect a normalized creator-detail payload from the active detail page."""

    metric_map = await _collect_labeled_map(
        page.locator(XingtuDetailSelectors.METRIC_BLOCKS),
        label_selector=XingtuDetailSelectors.METRIC_LABEL,
        value_selector=XingtuDetailSelectors.METRIC_VALUE,
    )
    raw_sections = await _collect_named_sections(page)
    header_tags = await _collect_all_texts(page.locator(XingtuDetailSelectors.HEADER_TAGS))
    page_text = await _safe_inner_text(page.locator(XingtuDetailSelectors.PAGE_BODY).first) or ""

    creator_name = await _extract_creator_name(page)
    xingtu_link = page.url
    core_metrics = _extract_core_metric_snapshot(page_text)
    fans_count = (
        _metric_int(metric_map, "粉丝量", "粉丝数", "粉丝")
        or _extract_labeled_scaled_number(page_text, "粉丝数")
        or _extract_labeled_scaled_number(page_text, "粉丝量")
    )

    return XingtuCreatorDetail(
        creator_name=creator_name,
        creator_id=_extract_creator_id(xingtu_link),
        xingtu_link=xingtu_link,
        creator_types=_dedupe_texts(header_tags),
        city=_search_value(raw_sections, ("上海", "北京", "广州", "深圳", "杭州", "成都")),
        fans_count=fans_count,
        female_ratio=_metric_ratio(metric_map, "女性占比", "女粉占比"),
        core_female_ratio=_metric_ratio(metric_map, "核心女粉占比", "核心女性占比"),
        price=_metric_currency(metric_map, "报价", "刊例价"),
        rebate=_metric_ratio(metric_map, "返点", "折扣"),
        settlement_price_est=_metric_currency(metric_map, "结算价", "预估结算价"),
        avg_video_play_median=core_metrics["avg_video_play_median"],
        avg_video_play_median_percentile=core_metrics["avg_video_play_median_percentile"],
        expected_cpm=core_metrics["expected_cpm"],
        average_completion_rate=core_metrics["average_completion_rate"],
        average_completion_rate_percentile=core_metrics["average_completion_rate_percentile"],
        average_interaction_rate=core_metrics["average_interaction_rate"],
        average_interaction_rate_percentile=core_metrics["average_interaction_rate_percentile"],
        monthly_connected_users=core_metrics["monthly_connected_users"],
        monthly_deep_users=core_metrics["monthly_deep_users"],
        median_commercial_play=_metric_int(metric_map, "商业视频中位播放", "视频中位播放") or core_metrics["avg_video_play_median"],
        natural_cpm=_metric_decimal(metric_map, "自然流量CPM", "自然CPM"),
        cpe=_metric_decimal(metric_map, "CPE"),
        commercial_completion_rate=_metric_ratio(metric_map, "商业完播率", "完播率") or core_metrics["average_completion_rate"],
        completion_cpm=_metric_decimal(metric_map, "完播CPM"),
        monthly_growth_rate=_metric_ratio(metric_map, "近30天涨粉率", "月涨粉率") or core_metrics["monthly_growth_rate"],
        broad_fan_ratio=_metric_ratio(metric_map, "泛粉占比", "泛兴趣人群占比"),
        deep_fan_ratio=_metric_ratio(metric_map, "深度粉丝占比", "深粉占比"),
        recent_curve_summary=_find_section_summary(raw_sections, "趋势", "涨粉", "曲线"),
        recent_content_summary=_find_section_summary(raw_sections, "近期作品", "内容", "推荐视频"),
        experience_tags=_extract_experience_tags(raw_sections),
        raw_metrics=metric_map,
        raw_sections=raw_sections,
    )


def validate_creator_detail(
    detail: XingtuCreatorDetail,
    required_fields: tuple[str, ...] = ("creator_name", "fans_count", "avg_video_play_median"),
) -> list[str]:
    """Return missing critical fields for the collected detail payload."""

    missing: list[str] = []
    for field_name in required_fields:
        value = getattr(detail, field_name, None)
        if value in (None, "", []):
            missing.append(field_name)
    return missing


async def dismiss_non_blocking_popups(page: Page) -> None:
    """Close known non-blocking popups without adding popup-specific branching."""

    for selector in OPTIONAL_POPUP_CLOSE_SELECTORS:
        locator = page.locator(selector)
        if not await locator.count():
            continue
        try:
            await locator.first.click(timeout=500)
            await page.wait_for_timeout(150)
        except Exception:
            continue


async def _apply_tag_filters(page: Page, section_title: str, values: list[str]) -> None:
    if not values:
        return

    section = _find_filter_section(page, section_title)
    if not await section.count():
        return

    for value in values:
        option = section.locator(XingtuFilterSelectors.TAG_OPTION).filter(has_text=value)
        await _click_if_visible(option.first)


async def _apply_dropdown_filter(page: Page, filter_name: str, values: list[str]) -> None:
    if not values:
        return

    trigger = _find_filter_group_trigger(page, filter_name)
    if not await trigger.count():
        return

    await trigger.click()
    await page.wait_for_timeout(200)
    menu = await _resolve_dropdown_menu(page)
    if menu is None:
        return

    for value in values:
        await _select_dropdown_option(menu, value)

    confirm_button = menu.locator(XingtuFilterSelectors.MENU_CONFIRM_BUTTON).first
    if await confirm_button.count():
        await _click_if_visible(confirm_button)
    else:
        await page.keyboard.press("Escape")

    await _best_effort_network_idle(page)


async def _apply_range_filter(page: Page, section_title: str, min_value: float | int | None, max_value: float | int | None) -> None:
    if min_value is None and max_value is None:
        return

    section = _find_filter_section(page, section_title)
    if not await section.count():
        return

    inputs = section.locator(XingtuFilterSelectors.RANGE_INPUTS)
    if min_value is not None and await inputs.count() >= 1:
        await _fill_if_visible(inputs.nth(0), str(min_value))
    if max_value is not None and await inputs.count() >= 2:
        await _fill_if_visible(inputs.nth(1), str(max_value))


async def _apply_sort(page: Page, sort_label: str) -> None:
    trigger = page.locator(XingtuFilterSelectors.SORT_TRIGGER).first
    if await trigger.count():
        await trigger.click()
        await page.get_by_role("option", name=sort_label).click()


def _find_filter_group_trigger(page: Page, filter_name: str) -> Locator:
    root = page.locator(XingtuFilterSelectors.ROOT).first
    try:
        return root.get_by_role("button", name=re.compile(fr"^{re.escape(filter_name)}(?:\s|$)")).first
    except Exception:
        return root.locator(XingtuFilterSelectors.GROUP_TRIGGER).filter(has_text=filter_name).first


def _find_filter_section(page: Page, section_title: str) -> Locator:
    return page.locator(XingtuFilterSelectors.SECTION_CONTAINER).filter(has_text=section_title).first


async def _resolve_dropdown_menu(page: Page) -> Locator | None:
    menus = page.locator(XingtuFilterSelectors.DROPDOWN_MENU)
    count = await menus.count()
    if count == 0:
        return None
    return menus.nth(count - 1)


async def _select_dropdown_option(menu: Locator, option_text: str) -> None:
    exact_role_option = menu.get_by_role("option", name=option_text)
    if await exact_role_option.count():
        await exact_role_option.first.click()
        return

    exact_menu_item = menu.get_by_role("menuitem", name=option_text)
    if await exact_menu_item.count():
        await exact_menu_item.first.click()
        return

    fallback_option = menu.locator(XingtuFilterSelectors.DROPDOWN_OPTION).filter(has_text=option_text).first
    await _click_if_visible(fallback_option)


async def _resolve_result_items(page: Page) -> Locator:
    content_root = page.locator(XingtuResultSelectors.CONTENT_ROOT).first
    rows = content_root.locator(XingtuResultSelectors.ROWS)
    if await rows.count():
        return rows
    return content_root.locator(XingtuResultSelectors.CLICKABLE_ITEMS)


async def _click_and_resolve_detail_page(page: Page, click_target: Locator) -> Page:
    popup_task = asyncio.create_task(page.wait_for_event("popup", timeout=1500))
    await click_target.click()

    try:
        detail_page = await popup_task
    except Exception:
        popup_task.cancel()
        await page.wait_for_timeout(600)
        detail_page = page

    return detail_page


async def _collect_labeled_map(blocks: Locator, label_selector: str, value_selector: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    count = await blocks.count()
    for index in range(count):
        block = blocks.nth(index)
        label = await _safe_inner_text(block.locator(label_selector).first)
        value = await _safe_inner_text(block.locator(value_selector).first)
        if label and value:
            mapping[label] = value
    return mapping


async def _collect_named_sections(page: Page) -> dict[str, str]:
    sections = page.locator(XingtuDetailSelectors.SECTION_BLOCKS)
    count = await sections.count()
    mapping: dict[str, str] = {}
    for index in range(count):
        section = sections.nth(index)
        title = await _safe_inner_text(section.locator(XingtuDetailSelectors.SECTION_TITLE).first)
        body = await _safe_inner_text(section.locator(XingtuDetailSelectors.SECTION_BODY).first)
        if title and body:
            mapping[title] = body
    return mapping


async def _collect_all_texts(locator: Locator) -> list[str]:
    values: list[str] = []
    count = await locator.count()
    for index in range(count):
        text = await _safe_inner_text(locator.nth(index))
        if text:
            values.append(text)
    return values


async def _safe_inner_text(locator: Locator) -> str | None:
    try:
        if not await locator.count():
            return None
        value = await locator.first.inner_text(timeout=500)
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned or None
    except Exception:
        return None


async def _safe_attribute(locator: Locator, attribute_name: str) -> str | None:
    try:
        if not await locator.count():
            return None
        return await locator.first.get_attribute(attribute_name, timeout=500)
    except Exception:
        return None


async def _click_if_visible(locator: Locator) -> None:
    try:
        if await locator.count():
            await locator.click(timeout=800)
    except Exception:
        return


async def _fill_if_visible(locator: Locator, value: str) -> None:
    try:
        if await locator.count():
            await locator.fill(value, timeout=800)
    except Exception:
        return


async def _best_effort_network_idle(page: Page) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=2000)
    except Exception:
        return


async def _pick_smallest_visible_locator(locator: Locator) -> Locator | None:
    count = await locator.count()
    best_index: int | None = None
    best_area: float | None = None

    for index in range(count):
        try:
            candidate = locator.nth(index)
            box = await candidate.bounding_box()
            if not box:
                continue
            if box["width"] < 20 or box["height"] < 20:
                continue
            area = box["width"] * box["height"]
            if best_area is None or area < best_area:
                best_area = area
                best_index = index
        except Exception:
            continue

    if best_index is None:
        return None
    return locator.nth(best_index)


def _extract_creator_id(text: str | None) -> str | None:
    if not text:
        return None
    patterns = (
        r"author-homepage/[^/]+/(\d{6,})",
        r"(?:author_id=|creator_id=|possessStarId=)(\d{6,})",
        r"/author/(\d{6,})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


async def _extract_creator_name(page: Page) -> str | None:
    selectors = (
        ".author-info .name",
        ".author-info",
        XingtuDetailSelectors.HEADER_NAME,
    )
    for selector in selectors:
        locator = page.locator(selector)
        count = await locator.count()
        for index in range(count):
            text = await _safe_inner_text(locator.nth(index))
            if _looks_like_creator_name(text):
                return text.split("星图ID", 1)[0].strip()
    return None


def _looks_like_creator_name(text: str | None) -> bool:
    if not text:
        return False
    candidate = re.sub(r"\s+", " ", text).strip()
    if not candidate or len(candidate) > 60:
        return False
    if any(token in candidate for token in ("能力", "概览", "合作行业", "粉丝数", "月连接用户数")):
        return False
    return True


def _account_name_regex(account_name: str) -> re.Pattern[str]:
    normalized = re.sub(r"\s+", "", account_name)
    match = re.search(r"^(.*?)(?:ID[:：]?)(\d+)$", normalized, re.IGNORECASE)
    if match:
        brand_name = re.escape(match.group(1))
        account_id = match.group(2)
        return re.compile(rf"{brand_name}\s*ID[:：]?\s*{account_id}")
    return re.compile(re.escape(account_name).replace(r"\ ", r"\s*"))


def _split_tags(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[/,，|]", text) if part.strip()]


def _dedupe_texts(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        deduped.append(value.strip())
        seen.add(normalized)
    return deduped


def _pick_text_like(values: list[str], snippets: tuple[str, ...]) -> str | None:
    lower_snippets = tuple(snippet.lower() for snippet in snippets)
    for value in values:
        if any(snippet in value.lower() for snippet in lower_snippets):
            return value
    return None


def _first_number_like(values: list[str], hints: tuple[str, ...]) -> int | None:
    for value in values:
        if any(hint.lower() in value.lower() for hint in hints):
            parsed = _parse_cn_int(value)
            if parsed is not None:
                return parsed
    return None


def _first_ratio_like(values: list[str], hints: tuple[str, ...]) -> float | None:
    for value in values:
        if any(hint.lower() in value.lower() for hint in hints):
            parsed = _parse_ratio(value)
            if parsed is not None:
                return parsed
    return None


def _first_currency_like(values: list[str]) -> float | None:
    for value in values:
        parsed = _parse_currency(value)
        if parsed is not None:
            return parsed
    return None


def _first_decimal_like(values: list[str], hints: tuple[str, ...]) -> float | None:
    for value in values:
        if any(hint.lower() in value.lower() for hint in hints):
            parsed = _parse_decimal(value)
            if parsed is not None:
                return parsed
    return None


def _metric_int(metric_map: dict[str, str], *aliases: str) -> int | None:
    value = _metric_text(metric_map, *aliases)
    return _parse_cn_int(value)


def _metric_ratio(metric_map: dict[str, str], *aliases: str) -> float | None:
    value = _metric_text(metric_map, *aliases)
    return _parse_ratio(value)


def _metric_currency(metric_map: dict[str, str], *aliases: str) -> float | None:
    value = _metric_text(metric_map, *aliases)
    return _parse_currency(value)


def _metric_decimal(metric_map: dict[str, str], *aliases: str) -> float | None:
    value = _metric_text(metric_map, *aliases)
    return _parse_decimal(value)


def _metric_text(metric_map: dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        for key, value in metric_map.items():
            if alias in key:
                return value
    return None


def _extract_core_metric_snapshot(page_text: str) -> dict[str, int | float | None]:
    return {
        "avg_video_play_median": _extract_labeled_scaled_number(page_text, "播放量中位数"),
        "avg_video_play_median_percentile": _extract_label_percentile(page_text, "播放量中位数"),
        "expected_cpm": _extract_labeled_scaled_number(page_text, "预期CPM"),
        "average_completion_rate": _extract_labeled_ratio(page_text, "完播率"),
        "average_completion_rate_percentile": _extract_label_percentile(page_text, "完播率"),
        "average_interaction_rate": _extract_labeled_ratio(page_text, "互动率"),
        "average_interaction_rate_percentile": _extract_label_percentile(page_text, "互动率"),
        "monthly_connected_users": _extract_labeled_scaled_number(page_text, "月连接用户数"),
        "monthly_deep_users": _extract_labeled_scaled_number(page_text, "月深度用户数"),
        "monthly_growth_rate": _extract_labeled_ratio(page_text, "月涨粉率"),
    }


def _parse_cn_int(text: str | None) -> int | None:
    number = _parse_scaled_number(text)
    return int(number) if number is not None else None


def _parse_currency(text: str | None) -> float | None:
    return _parse_scaled_number(text)


def _parse_decimal(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def _parse_ratio(text: str | None) -> float | None:
    if not text:
        return None
    clean = text.strip()
    match = re.search(r"-?\d+(?:\.\d+)?", clean.replace(",", ""))
    if not match:
        return None
    value = float(match.group(0))
    if "%" in clean:
        return value / 100
    return value if value <= 1 else value / 100


def _parse_scaled_number(text: str | None) -> float | None:
    if not text:
        return None

    clean = text.replace(",", "").strip().lower()
    match = re.search(r"-?\d+(?:\.\d+)?", clean)
    if not match:
        return None

    value = float(match.group(0))
    if "亿" in clean:
        value *= 100000000
    elif "万" in clean or clean.endswith("w"):
        value *= 10000
    return value


def _extract_labeled_scaled_number(page_text: str, label: str) -> int | float | None:
    match = re.search(rf"{re.escape(label)}[^\d]{{0,20}}([\d,.]+(?:w|万|亿)?)", page_text, re.IGNORECASE)
    if not match:
        return None
    return _parse_scaled_number(match.group(1))


def _extract_labeled_ratio(page_text: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}[^\d]{{0,20}}(\d+(?:\.\d+)?%?)", page_text, re.IGNORECASE)
    if not match:
        return None
    return _parse_ratio(match.group(1))


def _extract_label_percentile(page_text: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}.*?优于(\d+(?:\.\d+)?)%", page_text, re.IGNORECASE)
    if not match:
        return None
    return _parse_ratio(f"{match.group(1)}%")


def _find_section_summary(sections: dict[str, str], *keywords: str) -> str | None:
    for title, body in sections.items():
        if any(keyword in title for keyword in keywords):
            return body
    return None


def _extract_experience_tags(sections: dict[str, str]) -> list[str]:
    tags: list[str] = []
    for title, body in sections.items():
        if any(keyword in title for keyword in ("合作", "行业", "内容", "标签")):
            tags.extend(_split_tags(body))
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lower()
        if normalized in seen:
            continue
        deduped.append(tag)
        seen.add(normalized)
    return deduped


def _search_value(sections: dict[str, str], snippets: tuple[str, ...]) -> str | None:
    lower_snippets = tuple(snippet.lower() for snippet in snippets)
    for body in sections.values():
        if any(snippet in body.lower() for snippet in lower_snippets):
            return next((snippet for snippet in snippets if snippet.lower() in body.lower()), None)
    return None
