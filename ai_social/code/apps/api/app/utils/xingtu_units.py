from __future__ import annotations

import re


def parse_scaled_number(text: str | int | float | None) -> float | None:
    if text is None:
        return None
    if isinstance(text, int | float):
        return float(text)

    clean = str(text).strip().replace(",", "").replace("，", "").lower()
    if not clean or clean in {"-", "--", "—"}:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", clean)
    if not match:
        return None

    value = float(match.group(0))
    if "亿" in clean:
        value *= 100_000_000
    elif "万" in clean or clean.endswith("w"):
        value *= 10_000
    return value


def parse_int(text: str | int | float | None) -> int | None:
    value = parse_scaled_number(text)
    return int(round(value)) if value is not None else None


def parse_currency(text: str | int | float | None) -> float | None:
    return parse_scaled_number(text)


def parse_ratio(text: str | int | float | None) -> float | None:
    if text is None:
        return None
    if isinstance(text, int | float):
        value = float(text)
        return value if abs(value) <= 1 else value / 100

    clean = str(text).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", clean)
    if not match:
        return None
    value = float(match.group(0))
    if "%" in clean:
        return value / 100
    return value if abs(value) <= 1 else value / 100


def parse_decimal(text: str | int | float | None) -> float | None:
    if text is None:
        return None
    if isinstance(text, int | float):
        return float(text)
    clean = str(text).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", clean)
    return float(match.group(0)) if match else None


def compact_int(value: int | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if abs(value) >= 10_000:
        return f"{value / 10_000:.1f}万"
    return str(value)

