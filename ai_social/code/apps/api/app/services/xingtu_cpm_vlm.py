from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.xingtu_cpm import ScreenshotType, VlmExtractedPayload, VlmExtractionResult
from app.utils.xingtu_units import parse_currency, parse_decimal, parse_int, parse_ratio


DEFAULT_ARK_CODING_OPENAI_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
DEFAULT_VLM_MODEL = "doubao-seed-2.0-pro"


class VlmExtractor:
    model: str | None = None

    def extract_from_images(self, image_paths: list[Path], hints: dict[str, Any] | None = None) -> VlmExtractionResult:
        raise NotImplementedError


class VlmUnavailableError(RuntimeError):
    pass


class OpenAICompatibleVlmExtractor(VlmExtractor):
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract_from_images(self, image_paths: list[Path], hints: dict[str, Any] | None = None) -> VlmExtractionResult:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_content(image_paths, hints)},
            ],
        }
        if _getenv("XINGTU_CPM_VLM_RESPONSE_FORMAT", "none").strip().lower() == "json_object":
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"VLM request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"VLM request failed: {exc.reason}") from exc

        content = _extract_message_content(body)
        parsed, warning = parse_vlm_payload(content)
        return VlmExtractionResult(payload=parsed, model=self.model, warning=warning, raw_response=content)


def get_vlm_extractor(required: bool = False) -> VlmExtractor | None:
    enabled = _getenv("XINGTU_CPM_VLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    api_key = _getenv("XINGTU_CPM_VLM_API_KEY")
    if not enabled or not api_key:
        if required:
            raise VlmUnavailableError(vlm_config_warning())
        return None

    base_url = _getenv("XINGTU_CPM_VLM_BASE_URL", DEFAULT_ARK_CODING_OPENAI_BASE_URL)
    model = _getenv("XINGTU_CPM_VLM_MODEL", DEFAULT_VLM_MODEL)
    timeout = int(_getenv("XINGTU_CPM_VLM_TIMEOUT_SECONDS", "120"))
    return OpenAICompatibleVlmExtractor(base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout)


def is_vlm_configured() -> bool:
    return get_vlm_extractor(required=False) is not None


def vlm_config_warning() -> str:
    enabled = _getenv("XINGTU_CPM_VLM_ENABLED", "false").strip().lower()
    has_key = bool(_getenv("XINGTU_CPM_VLM_API_KEY"))
    if enabled not in {"1", "true", "yes", "on"}:
        return "VLM is not configured: set XINGTU_CPM_VLM_ENABLED=true and XINGTU_CPM_VLM_API_KEY."
    if not has_key:
        return "VLM is not configured: XINGTU_CPM_VLM_API_KEY is missing."
    return "VLM is configured."


def vlm_config_status() -> dict[str, Any]:
    enabled_value = _getenv("XINGTU_CPM_VLM_ENABLED", "false")
    enabled = enabled_value.strip().lower() in {"1", "true", "yes", "on"}
    return {
        "enabled": enabled,
        "has_api_key": bool(_getenv("XINGTU_CPM_VLM_API_KEY")),
        "base_url": _getenv("XINGTU_CPM_VLM_BASE_URL", DEFAULT_ARK_CODING_OPENAI_BASE_URL),
        "model": _getenv("XINGTU_CPM_VLM_MODEL", DEFAULT_VLM_MODEL),
        "configured": enabled and bool(_getenv("XINGTU_CPM_VLM_API_KEY")),
        "warning": vlm_config_warning(),
    }


def parse_vlm_payload(content: str) -> tuple[VlmExtractedPayload, str | None]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return VlmExtractedPayload(warnings=["VLM response was not valid JSON."]), "VLM response was not valid JSON."
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return VlmExtractedPayload(warnings=["VLM response JSON could not be parsed."]), "VLM response JSON could not be parsed."

    if not isinstance(data, dict):
        return VlmExtractedPayload(warnings=["VLM response JSON root was not an object."]), "VLM response JSON root was not an object."

    normalized, normalization_warnings = _normalize_vlm_data(_unwrap_vlm_data(data))
    try:
        payload = VlmExtractedPayload.model_validate(normalized)
    except ValidationError as exc:
        warning = f"VLM schema validation failed after normalization: {exc}"
        fallback = _fallback_payload_from_normalized(normalized)
        fallback.warnings.extend([*normalization_warnings, warning])
        return fallback, warning
    payload.warnings = [*normalization_warnings, *payload.warnings]
    return payload, None


def _extract_message_content(body: str) -> str:
    data = json.loads(body)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("VLM response had no choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    raise RuntimeError("VLM response message content was empty.")


def _unwrap_vlm_data(data: dict[str, Any]) -> dict[str, Any]:
    known_fields = {
        "detected_screenshot_types",
        "creator_name",
        "price_20s",
        "natural_plays",
        "sponsored_plays",
        "personal_chart_points",
        "star_chart_points",
    }
    current = data
    for key in ("payload", "data", "result", "extracted_fields"):
        if known_fields & set(current):
            return current
        nested = current.get(key)
        if isinstance(nested, dict):
            current = nested
    return current


def _normalize_vlm_data(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    normalized = dict(data)
    screenshot_type_values = {screenshot_type.value for screenshot_type in ScreenshotType}
    normalized["detected_screenshot_types"] = [
        mapped
        for item in (normalized.get("detected_screenshot_types") or [])
        if (mapped := _normalize_screenshot_type(item)) in screenshot_type_values
    ]
    if not normalized["detected_screenshot_types"]:
        normalized["detected_screenshot_types"] = _detected_types_from_screenshots(normalized.get("screenshots"))

    for key in ("price_20s", "price_20_60s", "price_60s_plus"):
        normalized[key] = _normalize_float_field(normalized.get(key), key, parse_currency, warnings)
    for key in (
        "post_count_30d",
        "platform_expected_play",
        "personal_chart_min_play",
        "personal_chart_max_play",
        "personal_chart_avg_play",
        "star_chart_min_play",
        "star_chart_max_play",
        "star_chart_avg_play",
        "ad_mode_play",
        "ad_median_play",
    ):
        normalized[key] = _normalize_int_field(normalized.get(key), key, warnings)
    normalized["platform_expected_cpm"] = _normalize_float_field(normalized.get("platform_expected_cpm"), "platform_expected_cpm", parse_decimal, warnings)
    normalized["monthly_fan_growth_rate"] = _normalize_float_field(normalized.get("monthly_fan_growth_rate"), "monthly_fan_growth_rate", parse_ratio, warnings)

    normalized["natural_plays"] = _normalize_play_list(normalized.get("natural_plays"), "natural_plays", warnings)
    normalized["sponsored_plays"] = _normalize_play_list(normalized.get("sponsored_plays"), "sponsored_plays", warnings)
    normalized["personal_chart_points"] = _normalize_chart_points(normalized.get("personal_chart_points"), "personal_chart_points", warnings)
    normalized["star_chart_points"] = _normalize_chart_points(normalized.get("star_chart_points"), "star_chart_points", warnings)

    for key in ("natural_plays", "sponsored_plays", "personal_chart_points", "star_chart_points", "screenshots", "warnings", "notes"):
        if normalized.get(key) is None:
            normalized[key] = []
    normalized["warnings"] = _normalize_string_list(normalized.get("warnings"))
    normalized["notes"] = _normalize_string_list(normalized.get("notes"))
    if normalized.get("chart_tabs_by_image") is None:
        normalized["chart_tabs_by_image"] = {}
    elif not isinstance(normalized.get("chart_tabs_by_image"), dict):
        warnings.append("VLM field chart_tabs_by_image was not an object and was dropped.")
        normalized["chart_tabs_by_image"] = {}
    else:
        normalized["chart_tabs_by_image"] = {str(key): str(value) for key, value in normalized["chart_tabs_by_image"].items() if value is not None}
    if normalized.get("screenshots") is None:
        normalized["screenshots"] = []
    elif not isinstance(normalized.get("screenshots"), list):
        warnings.append("VLM field screenshots was not a list and was dropped.")
        normalized["screenshots"] = []
    else:
        normalized["screenshots"] = [item for item in normalized["screenshots"] if isinstance(item, dict)]
    return normalized, warnings


def _fallback_payload_from_normalized(normalized: dict[str, Any]) -> VlmExtractedPayload:
    allowed = set(VlmExtractedPayload.model_fields)
    safe = {key: value for key, value in normalized.items() if key in allowed}
    for key in ("natural_plays", "sponsored_plays", "personal_chart_points", "star_chart_points", "screenshots", "warnings", "notes"):
        safe.setdefault(key, [])
    safe.setdefault("chart_tabs_by_image", {})
    try:
        return VlmExtractedPayload.model_validate(safe)
    except ValidationError:
        return VlmExtractedPayload(
            detected_screenshot_types=safe.get("detected_screenshot_types") or [],
            creator_name=safe.get("creator_name") if isinstance(safe.get("creator_name"), str) else None,
            natural_plays=safe.get("natural_plays") if isinstance(safe.get("natural_plays"), list) else [],
            sponsored_plays=safe.get("sponsored_plays") if isinstance(safe.get("sponsored_plays"), list) else [],
            warnings=["VLM response was partially unusable after normalization."],
        )


def _normalize_screenshot_type(value: Any) -> str:
    if isinstance(value, ScreenshotType):
        return value.value
    clean = str(value).strip().lower()
    aliases = {
        "overview": ScreenshotType.OVERVIEW_PRICING.value,
        "pricing": ScreenshotType.OVERVIEW_PRICING.value,
        "overview_pricing": ScreenshotType.OVERVIEW_PRICING.value,
        "报价": ScreenshotType.OVERVIEW_PRICING.value,
        "value": ScreenshotType.VALUE_PERSONAL_VIDEO.value,
        "value_personal_video": ScreenshotType.VALUE_PERSONAL_VIDEO.value,
        "传播价值": ScreenshotType.VALUE_PERSONAL_VIDEO.value,
        "personal_video": ScreenshotType.LATEST15_PERSONAL_CHART.value,
        "latest15_personal_chart": ScreenshotType.LATEST15_PERSONAL_CHART.value,
        "个人视频": ScreenshotType.LATEST15_PERSONAL_CHART.value,
        "star_video": ScreenshotType.LATEST15_STAR_CHART.value,
        "latest15_star_chart": ScreenshotType.LATEST15_STAR_CHART.value,
        "星图视频": ScreenshotType.LATEST15_STAR_CHART.value,
    }
    return aliases.get(clean, clean)


def _detected_types_from_screenshots(screenshots: Any) -> list[str]:
    if not isinstance(screenshots, list):
        return []
    detected: list[str] = []
    for item in screenshots:
        if not isinstance(item, dict):
            continue
        mapped = _normalize_screenshot_type(item.get("screenshot_type"))
        if mapped in {screenshot_type.value for screenshot_type in ScreenshotType} and mapped not in detected:
            detected.append(mapped)
    return detected


def _normalize_float_field(value: Any, field_name: str, parser, warnings: list[str]) -> float | None:
    if value is None or value == "":
        return None
    parsed = parser(value)
    if parsed is None:
        warnings.append(f"VLM field {field_name} could not be parsed and was dropped: {value!r}")
        return None
    return float(parsed)


def _normalize_int_field(value: Any, field_name: str, warnings: list[str]) -> int | None:
    if value is None or value == "":
        return None
    parsed = parse_int(value)
    if parsed is None:
        warnings.append(f"VLM field {field_name} could not be parsed and was dropped: {value!r}")
        return None
    return parsed


def _normalize_play_list(value: Any, field_name: str, warnings: list[str]) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append(f"VLM field {field_name} was not a list and was dropped.")
        return []
    plays: list[int] = []
    for index, item in enumerate(value):
        raw = item.get("play") if isinstance(item, dict) else item
        parsed = parse_int(raw)
        if parsed is None:
            warnings.append(f"VLM field {field_name}[{index}] could not be parsed and was dropped: {raw!r}")
            continue
        plays.append(parsed)
    return plays


def _normalize_chart_points(value: Any, field_name: str, warnings: list[str]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append(f"VLM field {field_name} was not a list and was dropped.")
        return []
    points: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            raw_play = item.get("play") or item.get("播放量") or item.get("value")
            play = parse_int(raw_play)
            if play is None:
                warnings.append(f"VLM field {field_name}[{index}].play could not be parsed and was dropped: {raw_play!r}")
                continue
            points.append(
                {
                    "date": str(item.get("date") or item.get("日期") or item.get("x") or "") or None,
                    "play": play,
                    "image_name": str(item.get("image_name") or item.get("image") or "") or None,
                }
            )
            continue
        play = parse_int(item)
        if play is None:
            warnings.append(f"VLM field {field_name}[{index}] could not be parsed and was dropped: {item!r}")
            continue
        points.append({"date": None, "play": play, "image_name": None})
    return points


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _user_content(image_paths: list[Path], hints: dict[str, Any] | None) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "请从这些巨量星图截图中提取结构化字段。"
                "只返回顶层 JSON object，不要 markdown，不要把结果包在 data/result/payload 里；识别不到就返回 null 或空数组；不要猜测。"
                "所有播放量和价格必须返回纯数字，不要带 w/万/亿/逗号/￥。"
                "如果包含 latest15 图表，请判断顶部 tab 是 all、personal_video 还是 star_video。"
                "个人视频 tab 的蓝色柱输出 natural_plays；星图视频 tab 的粉色柱输出 sponsored_plays；全部 tab 不要输出播放数组，只在 warnings 说明 all_tab_chart_deprecated。"
                "同时为个人视频图和星图视频图输出按横轴从左到右排序的 chart points，包含 date 和 play。"
                f"可用提示：{json.dumps(hints or {}, ensure_ascii=False)}"
            ),
        }
    ]
    for image_path in image_paths:
        mime = _mime_type(image_path)
        content.append({"type": "text", "text": f"image_name: {image_path.name}"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{_image_base64(image_path)}"},
            }
        )
    return content


def _image_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _system_prompt() -> str:
    return """
你是巨量星图商业数据截图的结构化提取器。你只能提取截图中明确可见的信息，不能猜测、不能补全。

必须只返回一个顶层 JSON object，不要 markdown，不要 ```json，不要包在 data/result/payload/extracted_fields 里。字段如下：
{
  "detected_screenshot_types": [],
  "creator_name": null,
  "price_20s": null,
  "price_20_60s": null,
  "price_60s_plus": null,
  "post_count_30d": null,
  "platform_expected_cpm": null,
  "platform_expected_play": null,
  "personal_chart_min_play": null,
  "personal_chart_max_play": null,
  "personal_chart_avg_play": null,
  "star_chart_min_play": null,
  "star_chart_max_play": null,
  "star_chart_avg_play": null,
  "ad_mode_play": null,
  "ad_median_play": null,
  "monthly_fan_growth_rate": null,
  "natural_plays": [],
  "sponsored_plays": [],
  "personal_chart_points": [],
  "star_chart_points": [],
  "screenshots": [],
  "chart_tabs_by_image": {},
  "warnings": [],
  "notes": []
}

detected_screenshot_types 只能使用：
overview_pricing, value_personal_video, latest15_personal_chart, latest15_star_chart。

单位规范：
- 所有播放量必须是整数，不要带 w/万/亿/逗号/中文单位；例如 “559.4w” 必须返回 5594000，“1,151.3万” 必须返回 11513000。
- 所有价格必须是纯数字，不要带 ￥ 或逗号；例如 “￥168,000” 必须返回 168000。
- 百分比转成小数，例如 -0.24% 转成 -0.0024。
- 图表读数数组必须按横轴从左到右排序。
- personal_chart_points/star_chart_points 的每一项必须形如 {"date":"26/03/06","play":5594000,"image_name":"xxx.png"}，也必须按横轴从左到右排序。
- 只有“个人视频”tab 的最新15图可以填 natural_plays。
- 只有“星图视频”tab 的最新15图可以填 sponsored_plays。
- 如果是“全部”tab，不要把混合柱状图填入 natural_plays 或 sponsored_plays，warnings 加 all_tab_chart_deprecated。
- 如果传播价值页没有明确“发布作品/发文数”，不要猜 post_count_30d；图表日期会由后端规则推导。
- 可以在 screenshots 中逐图记录 {"image_name":"xxx.png","screenshot_type":"...","chart_tab":"personal_video|star_video|all|null","warnings":[]}。

你不负责输出初级流量池、次级流量池、商单能力等级、预估商单播放量、CPM 或任何最终业务结论。
""".strip()


def _getenv(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    env_values = _read_dotenv_files()
    return env_values.get(name, default)


def _read_dotenv_files() -> dict[str, str]:
    values: dict[str, str] = {}
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path.cwd().parent.parent / ".env",
        Path(__file__).resolve().parents[4] / "local_only" / "env" / "apps_api.env",
        Path(__file__).resolve().parents[4] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                clean = line.strip()
                if not clean or clean.startswith("#") or "=" not in clean:
                    continue
                key, raw_value = clean.split("=", 1)
                key = key.strip()
                value = raw_value.strip().strip('"').strip("'")
                values.setdefault(key, value)
        except OSError:
            continue
    return values
