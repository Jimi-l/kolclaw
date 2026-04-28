from __future__ import annotations

import re
from typing import Iterable


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def normalize_text(value: str) -> str:
    cleaned = re.sub(r"[_\-/]+", " ", value.strip().lower())
    return re.sub(r"\s+", " ", cleaned)


def unique_list(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value.strip())
    return ordered


def overlap_score(source: Iterable[str], target: Iterable[str]) -> float:
    target_set = {normalize_text(item) for item in target if normalize_text(item)}
    if not target_set:
        return 0.0
    source_set = {normalize_text(item) for item in source if normalize_text(item)}
    return len(source_set & target_set) / len(target_set)


def contains_keywords(text: str, keywords: Iterable[str]) -> float:
    normalized_text = normalize_text(text)
    keyword_list = [normalize_text(keyword) for keyword in keywords if normalize_text(keyword)]
    if not keyword_list:
        return 0.0
    hits = sum(1 for keyword in keyword_list if keyword in normalized_text)
    return hits / len(keyword_list)


def scale_between(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.0
    scaled = (value - min_value) / (max_value - min_value)
    return clamp(scaled, 0.0, 1.0)


def inverse_scale_between(value: float, min_value: float, max_value: float) -> float:
    return 1.0 - scale_between(value, min_value, max_value)
