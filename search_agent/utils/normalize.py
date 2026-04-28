from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from search_agent.enums import HotnessAgeScore


COUNT_RE = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>亿|万|w|k|千)?", re.IGNORECASE)


def normalize_chinese_count(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower()
    if not text or text in {"--", "-", "暂无"}:
        return None
    text = text.replace(",", "").replace("+", "").replace("播放", "").replace("粉丝", "")
    match = COUNT_RE.search(text)
    if not match:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None
    number = float(match.group("number"))
    unit = match.group("unit") or ""
    multiplier = 1
    if unit in {"万", "w"}:
        multiplier = 10_000
    elif unit == "亿":
        multiplier = 100_000_000
    elif unit in {"k", "千"}:
        multiplier = 1_000
    return int(number * multiplier)


def format_chinese_count(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 100_000_000:
        formatted = f"{value / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}亿"
    if value >= 10_000:
        formatted = f"{value / 10_000:.1f}".rstrip("0").rstrip(".")
        return f"{formatted}万"
    return str(int(value))


def normalize_currency_value(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("元", "").replace("¥", "").replace("￥", "")
    if not text:
        return None
    match = COUNT_RE.search(text)
    if not match:
        return None
    number = float(match.group("number"))
    unit = match.group("unit") or ""
    multiplier = 1
    if unit in {"万", "w"}:
        multiplier = 10_000
    elif unit == "亿":
        multiplier = 100_000_000
    elif unit in {"k", "千"}:
        multiplier = 1_000
    return round(number * multiplier, 2)


def normalize_percentage_value(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_publish_date(raw_value: str | None, reference_date: date | None = None) -> str | None:
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None
    today = reference_date or date.today()
    if value in {"刚刚", "刚发布"}:
        return today.isoformat()
    if "小时前" in value or "分钟前" in value:
        return today.isoformat()
    if value == "昨天":
        return (today - timedelta(days=1)).isoformat()
    if value == "前天":
        return (today - timedelta(days=2)).isoformat()
    match = re.search(r"(\d+)\s*天前", value)
    if match:
        return (today - timedelta(days=int(match.group(1)))).isoformat()
    match = re.search(r"(\d{1,2})月(\d{1,2})日", value)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = today.year
        if (month, day) > (today.month, today.day):
            year -= 1
        return date(year, month, day).isoformat()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d"):
        try:
            parsed = datetime.strptime(value, pattern)
            if pattern.startswith("%Y"):
                return parsed.date().isoformat()
            candidate = date(today.year, parsed.month, parsed.day)
            if candidate > today:
                candidate = date(today.year - 1, parsed.month, parsed.day)
            return candidate.isoformat()
        except ValueError:
            continue
    return None


def score_hotness_age(raw_value: str | None, reference_date: date | None = None) -> str | None:
    normalized = normalize_publish_date(raw_value, reference_date=reference_date)
    if not normalized:
        return None
    today = reference_date or date.today()
    age_days = (today - date.fromisoformat(normalized)).days
    if age_days <= 1:
        return HotnessAgeScore.SCORE_100.value
    if age_days <= 3:
        return HotnessAgeScore.SCORE_90.value
    if age_days <= 7:
        return HotnessAgeScore.SCORE_80.value
    if age_days <= 15:
        return HotnessAgeScore.SCORE_70.value
    if age_days <= 30:
        return HotnessAgeScore.SCORE_60.value
    return HotnessAgeScore.SCORE_50.value
