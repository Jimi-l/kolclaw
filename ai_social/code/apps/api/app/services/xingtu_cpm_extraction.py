from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from fastapi import HTTPException

from app.schemas.xingtu_cpm import (
    REQUIRED_SCREENSHOT_TYPES,
    ChartPoint,
    ExtractedField,
    ScreenshotType,
    VlmExtractedPayload,
    XingtuCpmAnalyzeResponse,
    XingtuCpmInput,
    XingtuCpmParseResult,
    XingtuCpmRuleConfig,
)
from app.services.xingtu_cpm_rules import bucketed_mode, evaluate_xingtu_cpm
from app.services.xingtu_cpm_vlm import VlmExtractionResult, VlmUnavailableError, get_vlm_extractor


ExtractionMode = str


def parse_images(image_paths: list[Path], mode: ExtractionMode = "auto", config: XingtuCpmRuleConfig | None = None) -> XingtuCpmParseResult:
    config = config or XingtuCpmRuleConfig()
    resolved = _resolve_mode(mode)
    if resolved != "vlm_only":
        raise HTTPException(status_code=410, detail="Legacy extraction modes have been removed. Use VLM extraction.")
    return _parse_vlm_only(image_paths, config)


def analyze_images(image_paths: list[Path], mode: ExtractionMode = "auto", config: XingtuCpmRuleConfig | None = None) -> XingtuCpmAnalyzeResponse:
    config = config or XingtuCpmRuleConfig()
    parse_result = parse_images(image_paths, mode, config)
    assessment = evaluate_xingtu_cpm(parse_result.parsed_input, config)
    return XingtuCpmAnalyzeResponse(parse_result=parse_result, assessment=assessment)


def parse_vlm_extracted_payload(
    payload: VlmExtractedPayload,
    config: XingtuCpmRuleConfig | None = None,
    *,
    vlm_model_used: str | None = None,
    extraction_engine_used: str = "vlm",
    vlm_raw_response_preview: str | None = None,
) -> XingtuCpmParseResult:
    config = config or XingtuCpmRuleConfig()
    fields_by_type: dict[ScreenshotType, list[ExtractedField]] = {item: [] for item in ScreenshotType if item != ScreenshotType.UNKNOWN}
    for field in _fields_from_vlm_payload(payload, config):
        fields_by_type.setdefault(field.screenshot_type, []).append(field)

    all_fields = [field for fields in fields_by_type.values() for field in fields]
    parsed = _input_from_fields(all_fields)
    post_count_warnings = _derive_post_count_from_chart_dates(parsed)

    detected = sorted(set(payload.detected_screenshot_types) - {ScreenshotType.UNKNOWN}, key=lambda item: item.value)
    missing = [item for item in REQUIRED_SCREENSHOT_TYPES if item not in detected]
    notes = list(payload.notes)
    if missing:
        notes.append("缺少截图类型：" + ", ".join(item.value for item in missing))
    warnings = [*payload.warnings, *post_count_warnings]
    if _payload_is_empty(parsed):
        warnings.append("VLM returned a response but no usable fields were extracted. Check warnings and raw response preview.")

    field_sources = _field_sources_from_fields(all_fields)
    if parsed.post_count_30d_source == "chart_dates" and "post_count_30d" not in field_sources:
        field_sources["post_count_30d"] = "derived"

    return XingtuCpmParseResult(
        extraction_engine_used=extraction_engine_used,
        vlm_model_used=vlm_model_used,
        vlm_raw_response_preview=vlm_raw_response_preview,
        detected_screenshot_types=detected,
        missing_required_screenshot_types=missing,
        extracted_fields_by_screenshot_type={key: value for key, value in fields_by_type.items() if value},
        parsed_input=parsed,
        parser_notes=notes,
        warnings=warnings,
        field_sources=field_sources,
    )


def _resolve_mode(mode: ExtractionMode) -> ExtractionMode:
    requested = (mode or "auto").replace("-", "_").lower()
    if requested in {"auto", "vlm", "vlm_only"}:
        return "vlm_only"
    return requested


def _parse_vlm_only(image_paths: list[Path], config: XingtuCpmRuleConfig) -> XingtuCpmParseResult:
    vlm = _run_vlm(image_paths, required=True)
    result = parse_vlm_extracted_payload(
        vlm.payload,
        config,
        vlm_model_used=vlm.model,
        extraction_engine_used="vlm",
        vlm_raw_response_preview=_raw_response_preview(vlm.raw_response),
    )
    warnings = [item for item in [vlm.warning, *vlm.payload.warnings] if item]
    return result.model_copy(update={"warnings": _dedupe([*result.warnings, *warnings])})


def _run_vlm(image_paths: list[Path], required: bool) -> VlmExtractionResult:
    try:
        extractor = get_vlm_extractor(required=required)
    except VlmUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if extractor is None:
        raise HTTPException(status_code=503, detail="VLM is not configured.")
    try:
        return extractor.extract_from_images(image_paths)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"VLM extraction failed. {type(exc).__name__}: {exc}") from exc


def _fields_from_vlm_payload(payload: VlmExtractedPayload, config: XingtuCpmRuleConfig) -> list[ExtractedField]:
    fields: list[ExtractedField] = []
    scalar_map: dict[str, tuple[Any, ScreenshotType, str]] = {
        "creator_name": (payload.creator_name, ScreenshotType.OVERVIEW_PRICING, "vlm"),
        "price_20s": (payload.price_20s, ScreenshotType.OVERVIEW_PRICING, "vlm"),
        "price_20_60s": (payload.price_20_60s, ScreenshotType.OVERVIEW_PRICING, "vlm"),
        "price_60s_plus": (payload.price_60s_plus, ScreenshotType.OVERVIEW_PRICING, "vlm"),
        "post_count_30d": (payload.post_count_30d, ScreenshotType.VALUE_PERSONAL_VIDEO, "vlm"),
        "platform_expected_cpm": (payload.platform_expected_cpm, ScreenshotType.VALUE_PERSONAL_VIDEO, "vlm"),
        "platform_expected_play": (payload.platform_expected_play, ScreenshotType.VALUE_PERSONAL_VIDEO, "vlm"),
        "personal_chart_min_play": (payload.personal_chart_min_play, ScreenshotType.LATEST15_PERSONAL_CHART, "vlm"),
        "personal_chart_max_play": (payload.personal_chart_max_play, ScreenshotType.LATEST15_PERSONAL_CHART, "vlm"),
        "personal_chart_avg_play": (payload.personal_chart_avg_play, ScreenshotType.LATEST15_PERSONAL_CHART, "vlm"),
        "star_chart_min_play": (payload.star_chart_min_play, ScreenshotType.LATEST15_STAR_CHART, "vlm"),
        "star_chart_max_play": (payload.star_chart_max_play, ScreenshotType.LATEST15_STAR_CHART, "vlm"),
        "star_chart_avg_play": (payload.star_chart_avg_play, ScreenshotType.LATEST15_STAR_CHART, "vlm"),
        "monthly_fan_growth_rate": (payload.monthly_fan_growth_rate, ScreenshotType.OVERVIEW_PRICING, "vlm"),
    }
    for field_name, (value, screenshot_type, source) in scalar_map.items():
        if value is not None:
            fields.append(_field(field_name, value, screenshot_type, source=source))

    natural_plays = payload.natural_plays or [point.play for point in payload.personal_chart_points if point.play]
    sponsored_plays = payload.sponsored_plays or [point.play for point in payload.star_chart_points if point.play]
    for value in natural_plays:
        if value:
            fields.append(_field("natural_plays", value, ScreenshotType.LATEST15_PERSONAL_CHART, source="vlm"))
    for value in sponsored_plays:
        if value:
            fields.append(_field("sponsored_plays", value, ScreenshotType.LATEST15_STAR_CHART, source="vlm"))
    for point in payload.personal_chart_points:
        fields.append(_field("personal_chart_points", point, ScreenshotType.LATEST15_PERSONAL_CHART, source="vlm"))
    for point in payload.star_chart_points:
        fields.append(_field("star_chart_points", point, ScreenshotType.LATEST15_STAR_CHART, source="vlm"))

    sponsored_values = [value for value in sponsored_plays if value]
    if len(sponsored_values) >= config.min_valid_natural_plays:
        mode = bucketed_mode(sponsored_values, config)
        if mode is not None:
            fields.append(_field("ad_bucketed_mode_play", mode, ScreenshotType.LATEST15_STAR_CHART, source="derived"))
        fields.append(_field("ad_median_play", int(round(median(sorted(sponsored_values)))), ScreenshotType.LATEST15_STAR_CHART, source="derived"))
    elif payload.ad_mode_play is not None:
        fields.append(_field("ad_mode_play", payload.ad_mode_play, ScreenshotType.LATEST15_STAR_CHART, source="vlm"))
    if len(sponsored_values) < config.min_valid_natural_plays and payload.ad_median_play is not None:
        fields.append(_field("ad_median_play", payload.ad_median_play, ScreenshotType.LATEST15_STAR_CHART, source="vlm"))
    return fields


def _field(field_name: str, value: Any, screenshot_type: ScreenshotType, source: str) -> ExtractedField:
    raw_value = value.model_dump(mode="json") if isinstance(value, ChartPoint) else value
    return ExtractedField(
        field_name=field_name,
        raw_value=str(raw_value) if raw_value is not None else None,
        normalized_value=raw_value,
        source=source,  # type: ignore[arg-type]
        screenshot_type=screenshot_type,
        evidence_text=str(raw_value) if raw_value is not None else None,
    )


def _input_from_fields(fields: list[ExtractedField]) -> XingtuCpmInput:
    payload = XingtuCpmInput()
    for field in fields:
        if field.field_name == "natural_plays" and isinstance(field.normalized_value, int):
            payload.natural_plays.append(field.normalized_value)
        elif field.field_name == "sponsored_plays" and isinstance(field.normalized_value, int):
            payload.sponsored_plays.append(field.normalized_value)
        elif field.field_name == "personal_chart_points" and isinstance(field.normalized_value, dict):
            payload.personal_chart_points.append(ChartPoint.model_validate(field.normalized_value))
        elif field.field_name == "star_chart_points" and isinstance(field.normalized_value, dict):
            payload.star_chart_points.append(ChartPoint.model_validate(field.normalized_value))
        elif field.field_name == "post_count_30d":
            payload.post_count_30d = field.normalized_value
            payload.post_count_30d_source = "value_page"
        elif hasattr(payload, field.field_name):
            setattr(payload, field.field_name, field.normalized_value)
    return payload


def _derive_post_count_from_chart_dates(payload: XingtuCpmInput) -> list[str]:
    counts = _chart_post_count_30d(payload)
    if counts is None:
        if payload.post_count_30d is not None:
            payload.post_count_30d_source = payload.post_count_30d_source or "value_page"
        return []

    personal_count, star_count, total = counts
    payload.chart_date_count_30d_personal = personal_count
    payload.chart_date_count_30d_star = star_count
    payload.chart_date_count_30d_total = total

    previous = payload.post_count_30d
    payload.post_count_30d = total
    payload.post_count_30d_source = "chart_dates"
    if previous is not None and previous != total:
        return [f"VLM returned post_count_30d={previous}, but chart dates show {total} videos in the latest 30-day chart window; used chart_dates."]
    return []


def _chart_post_count_30d(payload: XingtuCpmInput) -> tuple[int, int, int] | None:
    dated_points = [
        *[(point, "personal") for point in payload.personal_chart_points],
        *[(point, "star") for point in payload.star_chart_points],
    ]
    parsed = [(point, kind, _parse_chart_date(point.date)) for point, kind in dated_points if point.play]
    parsed = [(point, kind, parsed_date) for point, kind, parsed_date in parsed if parsed_date is not None]
    if not parsed:
        return None
    latest = max(parsed_date for _, _, parsed_date in parsed)
    window_start = latest - timedelta(days=30)
    personal_count = sum(1 for _, kind, parsed_date in parsed if kind == "personal" and window_start <= parsed_date <= latest)
    star_count = sum(1 for _, kind, parsed_date in parsed if kind == "star" and window_start <= parsed_date <= latest)
    total = personal_count + star_count
    return personal_count, star_count, total


def _parse_chart_date(raw: str | None) -> date | None:
    if not raw:
        return None
    value = raw.strip().replace("-", "/")
    for fmt in ("%y/%m/%d", "%Y/%m/%d", "%m/%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            if fmt == "%m/%d":
                parsed = parsed.replace(year=date.today().year)
            return parsed.date()
        except ValueError:
            continue
    return None


def _field_sources_from_fields(fields: list[ExtractedField]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for field in fields:
        if field.field_name in sources and sources[field.field_name] != field.source:
            if "derived" in {sources[field.field_name], field.source}:
                sources[field.field_name] = "derived"
            else:
                sources[field.field_name] = field.source
        else:
            sources[field.field_name] = field.source
    return sources


def _dedupe(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _payload_is_empty(payload: XingtuCpmInput) -> bool:
    return not any(
        [
            payload.creator_name,
            payload.natural_plays,
            payload.sponsored_plays,
            payload.personal_chart_points,
            payload.star_chart_points,
            payload.post_count_30d is not None,
            payload.price_20s is not None,
            payload.price_20_60s is not None,
            payload.price_60s_plus is not None,
            payload.platform_expected_cpm is not None,
            payload.platform_expected_play is not None,
        ]
    )


def _raw_response_preview(raw_response: str | None) -> str | None:
    enabled = os.getenv("XINGTU_CPM_VLM_RAW_PREVIEW_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled or not raw_response:
        return None
    limit = int(os.getenv("XINGTU_CPM_VLM_RAW_PREVIEW_CHARS", "1200"))
    return raw_response[:limit]
