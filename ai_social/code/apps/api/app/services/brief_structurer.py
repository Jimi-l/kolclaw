from __future__ import annotations

import re
from datetime import date, timedelta

from app.schemas.brief import BriefConstraints, CampaignBrief
from app.utils.normalization import unique_list

KNOWN_CITIES = ["shanghai", "beijing", "guangzhou", "shenzhen", "hangzhou", "chengdu"]


def structure_brief_from_input(raw_text: str | None, structured_draft: CampaignBrief | None) -> tuple[CampaignBrief, list[str]]:
    if structured_draft:
        return structured_draft, ["Validated provided structured draft."]
    if not raw_text:
        raise ValueError("raw_text is required when structured_draft is omitted.")
    return parse_raw_brief(raw_text)


def parse_raw_brief(raw_text: str) -> tuple[CampaignBrief, list[str]]:
    text = raw_text.strip()
    notes = ["Parsed raw text with deterministic keyword and pattern rules."]
    lower = text.lower()

    platform = "douyin" if any(token in lower for token in ["douyin", "抖音"]) else "xiaohongshu"
    if platform == "douyin":
        notes.append("Detected platform `douyin` from brief text.")
    else:
        notes.append("Platform not explicit; defaulted to `xiaohongshu`.")

    budget_total = _extract_budget(lower) or 132000
    city = next((value for value in KNOWN_CITIES if value in lower), "shanghai")
    if city == "shanghai":
        notes.append("Detected Shanghai city fit or defaulted to Shanghai.")

    creator_types = unique_list(
        _collect_keywords(
            lower,
            ["fashion", "beauty", "stylish", "lifestyle", "dance", "pets", "parenting", "anime"],
        )
        or ["fashion", "beauty", "stylish"]
    )
    content_tags = unique_list(
        _collect_keywords(lower, ["outfit", "show", "transition", "runway", "vlog", "grwm", "street style"])
        or ["outfit", "show", "transition"]
    )
    style_tags = unique_list(
        _collect_keywords(lower, ["stylish", "premium", "city chic", "editorial", "minimal"])
        or ["stylish", "premium"]
    )

    event_date = _extract_date(lower) or date(2026, 5, 20)
    post_dates = [event_date, event_date + timedelta(days=1), event_date + timedelta(days=3)]
    notes.append(f"Using event date {event_date.isoformat()} for planning.")

    constraints = BriefConstraints(
        min_fans_count=80000,
        min_female_ratio=0.55,
        max_candidate_price=budget_total * 0.32,
        required_creator_types=creator_types,
        notes=["Initial scaffold uses simple default thresholds for raw-text parsing."],
    )

    brief = CampaignBrief(
        campaign_id="raw-brief-demo",
        campaign_name="Fashion Offline Event Demo",
        platform=platform,
        budget_total=budget_total,
        creator_tier="mid-tier",
        creator_types=creator_types,
        city=city,
        event_date=event_date,
        post_dates=post_dates,
        content_tags=content_tags,
        style_tags=style_tags,
        constraints=constraints,
        keywords=unique_list([city, "offline show", *creator_types, *content_tags, *style_tags]),
    )
    return brief, notes


def _extract_budget(text: str) -> float | None:
    patterns = [
        r"(?:budget|预算)[^\d]{0,8}([\d,]+(?:\.\d+)?)",
        r"([\d,]{4,}(?:\.\d+)?)\s*(?:rmb|cny|yuan|元)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _extract_date(text: str) -> date | None:
    iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    short_match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
    if short_match:
        month = int(short_match.group(1))
        day = int(short_match.group(2))
        return date(2026, month, day)
    return None


def _collect_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]
