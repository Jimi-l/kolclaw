from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_dir(path: str | Path) -> Path:
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def parse_cn_count(value: str | int | float | None) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().replace(",", "").replace("+", "")
    if not text:
        return None

    multiplier = 1
    if text.endswith("亿"):
        multiplier = 100_000_000
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10_000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def format_total_interactions(
    like_count: int,
    comment_count: int,
    share_count: int,
    favorite_count: int,
) -> str:
    return f"👍{like_count} 💬{comment_count} ↗️{share_count} ⭐{favorite_count}"


def days_to_freshness_score(days_since_publish: int) -> int:
    if days_since_publish <= 3:
        return 100
    if days_since_publish <= 5:
        return 90
    if days_since_publish <= 10:
        return 80
    if days_since_publish <= 15:
        return 70
    if days_since_publish <= 30:
        return 60
    return 50


def freshness_score_from_dates(
    publish_date: str | None,
    capture_date: str | None = None,
) -> Optional[int]:
    if not publish_date:
        return None

    capture_date = capture_date or datetime.now().strftime("%Y-%m-%d")
    accepted_formats = ("%Y-%m-%d", "%Y/%m/%d")

    parsed_publish = None
    parsed_capture = None
    for date_format in accepted_formats:
        if parsed_publish is None:
            try:
                parsed_publish = datetime.strptime(publish_date, date_format).date()
            except ValueError:
                pass
        if parsed_capture is None:
            try:
                parsed_capture = datetime.strptime(capture_date, date_format).date()
            except ValueError:
                pass

    if parsed_publish is None or parsed_capture is None:
        return None

    days_since_publish = max(0, (parsed_capture - parsed_publish).days)
    return days_to_freshness_score(days_since_publish)


def classify_traffic_trend(
    recommended_video_likes: int | None,
    recent_video_likes: Iterable[int],
) -> str:
    if not recommended_video_likes or recommended_video_likes <= 0:
        return "数据不足"

    recent = [value for value in recent_video_likes if value >= 0]
    if not recent:
        return "数据不足"

    recent_average = sum(recent) / len(recent)
    if recent_average < recommended_video_likes / 5:
        return "昙花一现"
    if recent_average < recommended_video_likes / 2:
        return "流量波动"
    return "持续爆款"


def dedupe_keep_order(items: Iterable[str], limit: int | None = None) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
        if limit is not None and len(results) >= limit:
            break
    return results


def configure_logger(name: str, log_dir: str | Path) -> logging.Logger:
    ensure_dir(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_path = Path(log_dir) / f"{name}.log"
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def load_prompt(prompt_name: str) -> str:
    prompt_path = PROJECT_ROOT / "prompts" / prompt_name
    return prompt_path.read_text(encoding="utf-8")
