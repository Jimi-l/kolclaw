from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


COUNT_RE = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>亿|万|w|k|千)?", re.IGNORECASE)
RECENT_LIKE_PREFIX = "recent_"
RECENT_LIKE_SUFFIX = "_like_count"
FOLLOWER_PRICE_BANDS = [
    (100_000, (0, 1_500), (1_500, 3_000), "under_100k"),
    (150_000, (2_300, 4_400), (4_400, 6_500), "100k_150k"),
    (200_000, (3_000, 5_500), (5_500, 8_000), "150k_200k"),
    (300_000, (4_000, 7_000), (7_000, 10_000), "200k_300k"),
    (500_000, (5_000, 9_350), (9_350, 13_700), "300k_500k"),
    (1_000_000, (7_800, 18_900), (18_900, 30_000), "500k_1m"),
    (2_000_000, (13_000, 25_500), (25_500, 38_000), "1m_2m"),
    (5_000_000, (23_200, 46_600), (46_600, 70_000), "2m_5m"),
    (8_000_000, (60_000, 130_000), (130_000, 200_000), "5m_8m"),
    (10_000_000, (85_000, 192_500), (192_500, 300_000), "8m_10m"),
]
FOLLOWER_PRICE_10M_PLUS = ((250_000, 375_000), (375_000, 500_000), "10m_plus")


@dataclass(frozen=True)
class CpeConfig:
    min_current_likes: int = 10_000
    focus_like_threshold: int = 30_000
    opportunity_ratio_floor: float = 1 / 20
    strong_ratio_floor: float = 1 / 10
    strong_cpe_ceiling: float = 0.8
    viable_cpe_ceiling: float = 1.5
    expensive_cpe_ceiling: float = 3.0


@dataclass(frozen=True)
class CreatorCpeAssessment:
    current_video_likes: int | None
    follower_count: int | None
    stable_like_median: int | None
    recent_like_sample_count: int
    estimated_price: float | None
    estimated_price_low: float | None
    estimated_price_high: float | None
    estimated_price_source: str
    price_data_quality: str
    like_cpe: float | None
    adjusted_cpe: float | None
    like_to_follower_ratio: float | None
    screening_status: str
    commercial_value_level: str
    attention_level: str
    reasons: list[str]


def assess_creator_row(
    row: dict[str, Any],
    config: CpeConfig | None = None,
    *,
    price_column: str | None = None,
    default_price: float | None = None,
) -> CreatorCpeAssessment:
    config = config or CpeConfig()
    current_likes = normalize_chinese_count(row.get("like_count_raw"))
    follower_count = normalize_chinese_count(row.get("profile_follower_count_raw"))
    recent_likes = _recent_like_counts(row)
    stable_like_median = int(round(median(recent_likes))) if recent_likes else current_likes
    like_to_follower_ratio = (
        round(stable_like_median / follower_count, 6)
        if stable_like_median is not None and follower_count and follower_count > 0
        else None
    )
    price_estimate = _price_from_row(
        row,
        follower_count=follower_count,
        stable_like_median=stable_like_median,
        current_likes=current_likes,
        like_to_follower_ratio=like_to_follower_ratio,
        config=config,
        price_column=price_column,
        default_price=default_price,
    )
    price = price_estimate.price

    like_cpe = round(price / stable_like_median, 4) if price is not None and stable_like_median and stable_like_median > 0 else None
    adjusted_cpe = _adjusted_cpe(like_cpe)

    reasons: list[str] = []
    screening_status = "kept"
    if current_likes is None:
        screening_status = "needs_review"
        reasons.append("当前视频点赞缺失，无法执行 1 万硬筛")
    elif current_likes < config.min_current_likes:
        screening_status = "excluded"
        reasons.append(f"当前视频点赞 {current_likes} < {config.min_current_likes}")

    attention_level = _attention_level(current_likes, stable_like_median, config)
    commercial_value_level = _commercial_value_level(
        screening_status=screening_status,
        adjusted_cpe=adjusted_cpe,
        stable_like_median=stable_like_median,
        like_to_follower_ratio=like_to_follower_ratio,
        config=config,
        reasons=reasons,
    )

    return CreatorCpeAssessment(
        current_video_likes=current_likes,
        follower_count=follower_count,
        stable_like_median=stable_like_median,
        recent_like_sample_count=len(recent_likes),
        estimated_price=price,
        estimated_price_low=price_estimate.price_low,
        estimated_price_high=price_estimate.price_high,
        estimated_price_source=price_estimate.source,
        price_data_quality=price_estimate.data_quality,
        like_cpe=like_cpe,
        adjusted_cpe=adjusted_cpe,
        like_to_follower_ratio=like_to_follower_ratio,
        screening_status=screening_status,
        commercial_value_level=commercial_value_level,
        attention_level=attention_level,
        reasons=reasons,
    )


def analyze_csv(
    input_path: Path,
    output_path: Path | None = None,
    config: CpeConfig | None = None,
    *,
    price_column: str | None = None,
    default_price: float | None = None,
) -> Path:
    config = config or CpeConfig()
    output_path = output_path or _default_output_path(input_path)

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {input_path}")

        fieldnames = [
            *reader.fieldnames,
            *_assessment_fieldnames(),
        ]
        rows = []
        for row in reader:
            assessment = assess_creator_row(
                row,
                config,
                price_column=price_column,
                default_price=default_price,
            )
            rows.append({**row, **_assessment_to_csv_fields(assessment)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def analyze_csvs(
    input_paths: list[Path],
    output_path: Path | None = None,
    config: CpeConfig | None = None,
    *,
    price_column: str | None = None,
    default_price: float | None = None,
) -> Path:
    if not input_paths:
        raise ValueError("At least one input CSV is required.")
    if len(input_paths) == 1:
        return analyze_csv(
            input_paths[0],
            output_path,
            config,
            price_column=price_column,
            default_price=default_price,
        )

    config = config or CpeConfig()
    output_path = output_path or _default_combined_output_path(input_paths)
    rows: list[dict[str, Any]] = []
    fieldnames: list[str] = []

    for input_path in input_paths:
        with input_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None:
                raise ValueError(f"CSV has no header: {input_path}")
            fieldnames = _merge_fieldnames(fieldnames, ["source_csv", *reader.fieldnames, *_assessment_fieldnames()])
            for row in reader:
                assessment = assess_creator_row(
                    row,
                    config,
                    price_column=price_column,
                    default_price=default_price,
                )
                rows.append(
                    {
                        "source_csv": input_path.name,
                        **row,
                        **_assessment_to_csv_fields(assessment),
                    }
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def _recent_like_counts(row: dict[str, Any]) -> list[int]:
    counts: list[int] = []
    for key, value in row.items():
        if key.startswith(RECENT_LIKE_PREFIX) and key.endswith(RECENT_LIKE_SUFFIX):
            normalized = normalize_chinese_count(value)
            if normalized is not None and normalized > 0:
                counts.append(normalized)
    return counts


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


@dataclass(frozen=True)
class PriceEstimate:
    price: float | None
    price_low: float | None
    price_high: float | None
    source: str
    data_quality: str


def _price_from_row(
    row: dict[str, Any],
    *,
    follower_count: int | None,
    stable_like_median: int | None,
    current_likes: int | None,
    like_to_follower_ratio: float | None,
    config: CpeConfig,
    price_column: str | None,
    default_price: float | None,
) -> PriceEstimate:
    if price_column:
        price = normalize_currency_value(row.get(price_column))
        return PriceEstimate(price, price, price, f"price_column:{price_column}", "manual")
    if default_price is not None:
        return PriceEstimate(default_price, default_price, default_price, "default_price", "manual")
    return _estimate_price_from_followers(
        follower_count=follower_count,
        stable_like_median=stable_like_median,
        current_likes=current_likes,
        like_to_follower_ratio=like_to_follower_ratio,
        config=config,
    )


def _estimate_price_from_followers(
    *,
    follower_count: int | None,
    stable_like_median: int | None,
    current_likes: int | None,
    like_to_follower_ratio: float | None,
    config: CpeConfig,
) -> PriceEstimate:
    data_quality = _price_data_quality(
        stable_like_median=stable_like_median,
        current_likes=current_likes,
        like_to_follower_ratio=like_to_follower_ratio,
        config=config,
    )
    if follower_count is None:
        return PriceEstimate(None, None, None, "estimated_by_follower_band", data_quality)

    for upper_bound, average_range, good_range, band_name in FOLLOWER_PRICE_BANDS:
        if follower_count < upper_bound:
            price_low, price_high = good_range if data_quality == "good" else average_range
            return PriceEstimate(
                _range_midpoint(price_low, price_high),
                float(price_low),
                float(price_high),
                f"estimated_by_follower_band:{band_name}",
                data_quality,
            )

    average_range, good_range, band_name = FOLLOWER_PRICE_10M_PLUS
    price_low, price_high = good_range if data_quality == "good" else average_range
    return PriceEstimate(
        _range_midpoint(price_low, price_high),
        float(price_low),
        float(price_high),
        f"estimated_by_follower_band:{band_name}",
        data_quality,
    )


def _price_data_quality(
    *,
    stable_like_median: int | None,
    current_likes: int | None,
    like_to_follower_ratio: float | None,
    config: CpeConfig,
) -> str:
    _ = stable_like_median, current_likes
    if like_to_follower_ratio is not None and like_to_follower_ratio >= config.opportunity_ratio_floor:
        return "good"
    return "average"


def _range_midpoint(price_low: int | float, price_high: int | float) -> float:
    return round((float(price_low) + float(price_high)) / 2, 2)


def _attention_level(current_likes: int | None, stable_like_median: int | None, config: CpeConfig) -> str:
    signal = max(value for value in (current_likes, stable_like_median) if value is not None) if current_likes or stable_like_median else None
    if signal is None:
        return "unknown"
    if signal >= config.focus_like_threshold:
        return "focus_30k_plus"
    if signal >= config.min_current_likes:
        return "watch_10k_plus"
    return "low_like"


def _adjusted_cpe(like_cpe: float | None) -> float | None:
    if like_cpe is None:
        return None
    if 0 <= like_cpe < 1:
        multiplier = 2.4
    elif 1 <= like_cpe < 2:
        multiplier = 1.8
    elif 2 <= like_cpe < 3:
        multiplier = 1.4
    else:
        multiplier = 1.0
    return round(like_cpe * multiplier, 4)


def _commercial_value_level(
    *,
    screening_status: str,
    adjusted_cpe: float | None,
    stable_like_median: int | None,
    like_to_follower_ratio: float | None,
    config: CpeConfig,
    reasons: list[str],
) -> str:
    if screening_status == "excluded":
        return "no_commercial_value"

    if stable_like_median is None:
        reasons.append("缺少可用近期点赞，无法计算稳定点赞中位数")
        return "needs_review"

    if like_to_follower_ratio is not None:
        if like_to_follower_ratio >= config.strong_ratio_floor:
            reasons.append("稳定点赞 >= 粉丝数 1/10，互动效率强")
        elif like_to_follower_ratio >= config.opportunity_ratio_floor:
            reasons.append("稳定点赞 >= 粉丝数 1/20，有合作机会")
        else:
            reasons.append("稳定点赞 / 粉丝数低于 1/20，粉丝转化偏弱")
    else:
        reasons.append("粉丝数缺失，未计算点赞粉丝比")

    if adjusted_cpe is None:
        reasons.append("报价缺失，暂不能计算 adjusted_cpe")
        return "needs_price"
    if adjusted_cpe <= config.strong_cpe_ceiling:
        reasons.append(f"adjusted_cpe {adjusted_cpe} <= {config.strong_cpe_ceiling}")
        return "strong_value"
    if adjusted_cpe <= config.viable_cpe_ceiling:
        reasons.append(f"adjusted_cpe {adjusted_cpe} <= {config.viable_cpe_ceiling}")
        return "viable_value"
    if adjusted_cpe <= config.expensive_cpe_ceiling:
        reasons.append(f"adjusted_cpe {adjusted_cpe} <= {config.expensive_cpe_ceiling}，偏贵需复核")
        return "expensive_review"

    reasons.append(f"adjusted_cpe {adjusted_cpe} > {config.expensive_cpe_ceiling}")
    return "no_commercial_value"


def _assessment_to_csv_fields(assessment: CreatorCpeAssessment) -> dict[str, str | int | float | None]:
    return {
        "current_video_likes_normalized": assessment.current_video_likes,
        "follower_count_normalized": assessment.follower_count,
        "stable_like_median": assessment.stable_like_median,
        "recent_like_sample_count": assessment.recent_like_sample_count,
        "estimated_price": assessment.estimated_price,
        "estimated_price_low": assessment.estimated_price_low,
        "estimated_price_high": assessment.estimated_price_high,
        "estimated_price_source": assessment.estimated_price_source,
        "price_data_quality": assessment.price_data_quality,
        "like_cpe": assessment.like_cpe,
        "adjusted_cpe": assessment.adjusted_cpe,
        "like_to_follower_ratio": assessment.like_to_follower_ratio,
        "screening_status": assessment.screening_status,
        "commercial_value_level": assessment.commercial_value_level,
        "attention_level": assessment.attention_level,
        "cpe_reasons": "；".join(assessment.reasons),
    }


def _assessment_fieldnames() -> list[str]:
    return [
        "current_video_likes_normalized",
        "follower_count_normalized",
        "stable_like_median",
        "recent_like_sample_count",
        "estimated_price",
        "estimated_price_low",
        "estimated_price_high",
        "estimated_price_source",
        "price_data_quality",
        "like_cpe",
        "adjusted_cpe",
        "like_to_follower_ratio",
        "screening_status",
        "commercial_value_level",
        "attention_level",
        "cpe_reasons",
    ]


def _merge_fieldnames(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    seen = set(existing)
    for fieldname in incoming:
        if fieldname not in seen:
            merged.append(fieldname)
            seen.add(fieldname)
    return merged


def _default_output_path(input_path: Path) -> Path:
    stem = input_path.stem.replace("discovery_summary", "cpe_summary")
    if stem == input_path.stem:
        stem = f"{input_path.stem}_cpe_summary"
    return input_path.with_name(f"{stem}.csv")


def _default_combined_output_path(input_paths: list[Path]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return input_paths[0].parent / f"cpe_summary_combined_{timestamp}.csv"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate like-based creator CPE from a discovery summary CSV.")
    parser.add_argument("input_csv", type=Path, nargs="+", help="One or more discovery_summary CSV paths.")
    parser.add_argument("-o", "--output", type=Path, help="Path for enriched CPE CSV output.")
    parser.add_argument("--price-column", help="CSV column containing creator price. If omitted, CPE is only calculated when --default-price is set.")
    parser.add_argument("--default-price", type=float, help="Fallback price used for every creator when no price column exists.")
    parser.add_argument("--min-current-likes", type=int, default=10_000, help="Exclude creators below this current-video like count.")
    parser.add_argument("--focus-like-threshold", type=int, default=30_000, help="Mark creators at or above this like count as focus accounts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = CpeConfig(
        min_current_likes=args.min_current_likes,
        focus_like_threshold=args.focus_like_threshold,
    )
    output_path = analyze_csvs(
        args.input_csv,
        args.output,
        config,
        price_column=args.price_column,
        default_price=args.default_price,
    )
    print(f"Wrote CPE summary: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
