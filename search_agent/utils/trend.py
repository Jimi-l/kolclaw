from __future__ import annotations

from search_agent.enums import TrafficTrend
from search_agent.utils.normalize import format_chinese_count, normalize_chinese_count


def classify_traffic_trend(
    recommendation_like: str | int | None,
    recent_likes: list[str | int | None],
) -> tuple[TrafficTrend | None, str | None, str | None]:
    recommendation_value = normalize_chinese_count(recommendation_like)
    normalized_recent = [normalize_chinese_count(value) for value in recent_likes]
    valid_recent = [value for value in normalized_recent if value is not None]
    if recommendation_value is None or len(valid_recent) < 2:
        return None, "推荐视频点赞或近3条点赞信息不足，无法稳定判断流量趋势", None

    avg_recent = int(sum(valid_recent) / len(valid_recent))
    ratio = avg_recent / recommendation_value if recommendation_value else 0
    avg_recent_raw = format_chinese_count(avg_recent)

    if ratio < 0.35:
        return (
            TrafficTrend.FLASH,
            "近期平均点赞显著低于推荐视频，判断为偶发爆款",
            avg_recent_raw,
        )
    if ratio < 0.75:
        return (
            TrafficTrend.VOLATILE,
            "近期3条平均点赞低于当前推荐视频，但仍保有一定起量能力，判断为流量波动",
            avg_recent_raw,
        )
    return (
        TrafficTrend.SUSTAINED,
        "近期内容连续维持较高点赞，判断为持续爆款",
        avg_recent_raw,
    )
