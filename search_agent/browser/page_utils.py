from __future__ import annotations

from typing import Any, Iterable


def first_visible_locator(scope: Any, selectors: Iterable[str], timeout_ms: int = 800) -> Any | None:
    for selector in selectors:
        try:
            locator = scope.locator(selector).first
            if locator.count() and locator.is_visible(timeout=timeout_ms):
                return locator
        except Exception:
            continue
    return None


def first_text(scope: Any, selectors: Iterable[str], timeout_ms: int = 800) -> str | None:
    locator = first_visible_locator(scope, selectors, timeout_ms=timeout_ms)
    if locator is None:
        return None
    try:
        text = locator.inner_text(timeout=timeout_ms).strip()
        return text or None
    except Exception:
        return None


def first_attribute(scope: Any, selectors: Iterable[str], attribute: str, timeout_ms: int = 800) -> str | None:
    locator = first_visible_locator(scope, selectors, timeout_ms=timeout_ms)
    if locator is None:
        return None
    try:
        value = locator.get_attribute(attribute, timeout=timeout_ms)
        return value.strip() if value else None
    except Exception:
        return None


def locator_text(locator: Any, timeout_ms: int = 800) -> str | None:
    try:
        text = locator.inner_text(timeout=timeout_ms).strip()
        return text or None
    except Exception:
        return None


def body_text(page: Any, timeout_ms: int = 1_000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout_ms)
    except Exception:
        return ""


def page_contains_any_text(page: Any, phrases: Iterable[str]) -> str | None:
    haystack = body_text(page).lower()
    for phrase in phrases:
        if phrase.lower() in haystack:
            return phrase
    return None
