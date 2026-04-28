from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Tuple

from app.schemas.xingtu_cpm import (
    CommercialAbilityMetrics,
    CpmTierResult,
    PoolEstimate,
    TrendMetrics,
    XingtuCpmAssessment,
    XingtuCpmInput,
    XingtuCpmRuleConfig,
)


@dataclass(frozen=True)
class _WeightedPlaySample:
    play: int
    weight: float
    parsed_date: date | None = None


def bucketed_mode(values: list[int], config: XingtuCpmRuleConfig) -> int | None:
    cleaned = sorted(value for value in values if value and value > 0)
    if not cleaned:
        return None

    bucket_config = config.bucketed_mode
    width = max(bucket_config.min_bucket_width, int(median(cleaned) * bucket_config.bucket_ratio))
    buckets: dict[int, list[int]] = {}
    for value in cleaned:
        bucket_key = int(value // width)
        buckets.setdefault(bucket_key, []).append(value)

    ranked = sorted(
        buckets.items(),
        key=lambda item: (
            len(item[1]),
            -item[0] if bucket_config.prefer_lower_bucket_on_tie else item[0],
        ),
        reverse=True,
    )
    return int(round(median(ranked[0][1])))


def evaluate_xingtu_cpm(payload: XingtuCpmInput, config: XingtuCpmRuleConfig | None = None) -> XingtuCpmAssessment:
    config = config or XingtuCpmRuleConfig()
    review_reasons: list[str] = []
    explanations: list[str] = []
    confidence = config.confidence.initial_score

    effective_post_count, post_count_source, chart_counts = _effective_post_count(payload)
    natural_plays_ordered = _ordered_plays_from_points(payload.personal_chart_points, payload.natural_plays)
    sponsored_plays_ordered = _ordered_plays_from_points(payload.star_chart_points, payload.sponsored_plays)
    overall_ordered = _overall_ordered_plays(payload)
    natural_plays = _clean_plays(payload.natural_plays)
    sponsored_plays = _clean_plays(payload.sponsored_plays)
    if len(natural_plays) < config.min_valid_natural_plays:
        review_reasons.append(f"自然播放量有效值少于 {config.min_valid_natural_plays} 个")
        confidence -= config.confidence.low_natural_count_penalty
    if len(sponsored_plays) < config.min_valid_natural_plays:
        review_reasons.append(f"星图视频播放量有效值少于 {config.min_valid_natural_plays} 个")
        confidence -= config.confidence.missing_required_field_penalty

    if effective_post_count is None:
        review_reasons.append("缺少近30天发文数")
        confidence -= config.confidence.missing_required_field_penalty
    elif effective_post_count == 0:
        review_reasons.append("近30天发文数为0，按无商业价值处理")
        return XingtuCpmAssessment(
            primary_pool=PoolEstimate(explanation="近30天发文数为0，未计算流量池"),
            secondary_pool=None,
            commercial_level="NO_COMMERCIAL_VALUE",
            confidence_score=max(0, confidence - config.confidence.very_low_post_count_penalty),
            review_flag=True,
            review_reasons=review_reasons,
            explanations=["近30天发文数为0，规则直接判定暂不计算 CPM。"],
            reference={"platform_expected_cpm": payload.platform_expected_cpm, "platform_expected_play": payload.platform_expected_play},
            debug={"valid_natural_plays": natural_plays, "post_count_30d_source": post_count_source, **chart_counts},
        )
    elif effective_post_count <= 2:
        confidence -= config.confidence.very_low_post_count_penalty
        review_reasons.append("近30天发文数过少")
    elif effective_post_count < 6:
        confidence -= config.confidence.low_post_count_penalty
        review_reasons.append("近30天发文数不足6条，已进行折损")

    has_sponsored_stats = len(sponsored_plays) >= config.min_valid_natural_plays
    missing_commercial_fields = [] if has_sponsored_stats else [
        name
        for name, value in (
            ("星图序列派生中位数", payload.ad_median_play),
            ("星图序列派生分桶众数", payload.ad_bucketed_mode_play or payload.ad_mode_play),
        )
        if value is None
    ]
    if missing_commercial_fields:
        confidence -= config.confidence.missing_required_field_penalty * len(missing_commercial_fields)
        review_reasons.extend(f"缺少 {name}" for name in missing_commercial_fields)

    raw_primary, raw_secondary = _find_pools(natural_plays, config, payload.personal_chart_points)
    raw_commercial_primary, raw_commercial_secondary = _find_pools(sponsored_plays, config, payload.star_chart_points)
    factor = _post_discount_factor(effective_post_count, config)
    primary = raw_primary
    secondary = raw_secondary
    commercial_primary = raw_commercial_primary if sponsored_plays else None
    commercial_secondary = raw_commercial_secondary if sponsored_plays and raw_commercial_secondary else None

    if secondary is None:
        confidence -= config.confidence.no_secondary_pool_penalty
        review_reasons.append("无法稳定识别次级流量池")
    elif secondary.is_estimated:
        confidence -= config.confidence.no_secondary_pool_penalty / 2
        review_reasons.append("次级流量池为分位估算，建议复核")
    if commercial_secondary and commercial_secondary.is_estimated:
        confidence -= config.confidence.no_secondary_pool_penalty / 2
        review_reasons.append("星图商单次级池为分位估算，建议复核")

    derived_ad_mode = bucketed_mode(sponsored_plays, config) if len(sponsored_plays) >= config.min_valid_natural_plays else None
    derived_ad_median = int(round(median(sponsored_plays))) if len(sponsored_plays) >= config.min_valid_natural_plays else None
    ad_mode = derived_ad_mode if derived_ad_mode is not None else payload.ad_bucketed_mode_play or payload.ad_mode_play
    ad_median = derived_ad_median if derived_ad_median is not None else payload.ad_median_play
    if ad_mode and ad_median and max(ad_mode, ad_median) / max(1, min(ad_mode, ad_median)) > config.ad_stat_divergence_ratio:
        confidence -= config.confidence.ad_stat_divergence_penalty
        review_reasons.append("商单分桶众数和中位数差异过大")

    ad_repr_play = _ad_repr_play(ad_median, ad_mode, config)
    commercial_cpm_play_basis, commercial_play_basis_source = _commercial_cpm_play_basis(commercial_primary, commercial_secondary, ad_repr_play)
    natural_cpm_play_basis = primary.center

    natural_trend_metrics = _analyze_traffic_trend(natural_plays_ordered, config)
    commercial_trend_metrics = _analyze_traffic_trend(sponsored_plays_ordered, config)
    overall_trend_metrics = _analyze_traffic_trend(overall_ordered, config)
    weighted_predicted_ad_play, commercial_ability, base_predicted_play, final_factors = _predict_ad_play_weighted(
        sponsored_plays,
        primary,
        secondary,
        commercial_primary,
        commercial_secondary,
        ad_repr_play,
        overall_trend_metrics,
        config,
    )

    if commercial_cpm_play_basis is None:
        commercial_cpm_play_basis = weighted_predicted_ad_play
        commercial_play_basis_source = "weighted_prediction"
    predicted_ad_play = commercial_cpm_play_basis

    commercial_level = _commercial_level_from_commercial_pool(commercial_cpm_play_basis, primary, secondary)

    if commercial_cpm_play_basis and primary.center and commercial_cpm_play_basis < primary.center * 0.8:
        confidence -= config.confidence.ad_stat_divergence_penalty
        review_reasons.append("星图视频表现弱于自然基线")
    if payload.platform_expected_play and payload.platform_expected_play < 10_000:
        review_reasons.append("平台预期播放异常，已忽略平台预期播放差异判断")
    elif payload.platform_expected_play and commercial_cpm_play_basis:
        ratio = max(payload.platform_expected_play, commercial_cpm_play_basis) / max(1, min(payload.platform_expected_play, commercial_cpm_play_basis))
        if ratio > config.ad_stat_divergence_ratio:
            confidence -= config.confidence.ad_stat_divergence_penalty
            review_reasons.append("星图池与平台预期播放差异过大")

    _check_chart_summary(payload.personal_chart_avg_play, natural_plays, "个人视频图表均值", review_reasons, config)
    _check_chart_summary(payload.star_chart_avg_play, sponsored_plays, "星图视频图表均值", review_reasons, config)

    for price_name, price_value in _prices(payload).items():
        if price_value is None:
            confidence -= config.confidence.price_issue_penalty
            review_reasons.append(f"缺少 {price_name} 报价")
            continue
        if price_value < config.price_min or price_value > config.price_max:
            confidence -= config.confidence.price_issue_penalty
            review_reasons.append(f"{price_name} 报价异常")

    cpm_by_tier = _calculate_cpms(payload, commercial_cpm_play_basis, natural_cpm_play_basis, commercial_play_basis_source)
    explanations.extend(_build_explanations(primary, secondary, ad_repr_play, predicted_ad_play, factor))
    if commercial_primary:
        explanations.append(commercial_primary.explanation.replace("初级流量池", "星图商单流量池"))
    else:
        explanations.append("未识别到星图视频播放序列，商单 CPM 使用商单代表值兜底。")

    explanations.append(f"商单能力评估：{commercial_ability.explanation}，系数={commercial_ability.coefficient}")
    explanations.append(f"自然流量趋势：{natural_trend_metrics.trend_direction}，系数={natural_trend_metrics.trend_coefficient:.2f}")
    explanations.append(f"星图流量趋势：{commercial_trend_metrics.trend_direction}，系数={commercial_trend_metrics.trend_coefficient:.2f}")
    explanations.append(f"全部流量趋势：{overall_trend_metrics.trend_direction}，系数={overall_trend_metrics.trend_coefficient:.2f}")
    explanations.append("互动修正系数暂未启用，当前固定为 1.0。")
    if post_count_source == "chart_dates":
        explanations.append("近30天发文数由个人视频和星图视频图表日期推导。")
    if primary.age_weighted or (commercial_primary and commercial_primary.age_weighted):
        explanations.append("流量池中心已按图表日期做时间衰减加权，近期视频权重更高。")

    confidence = max(0.0, min(100.0, round(confidence, 2)))
    review_flag = bool(review_reasons) or confidence < config.confidence.review_threshold

    return XingtuCpmAssessment(
        primary_pool=primary,
        secondary_pool=secondary,
        commercial_primary_pool=commercial_primary,
        commercial_secondary_pool=commercial_secondary,
        commercial_cpm_play_basis=commercial_cpm_play_basis,
        natural_cpm_play_basis=natural_cpm_play_basis,
        commercial_pool_center_for_cpm=commercial_cpm_play_basis,
        natural_pool_center_for_cpm=natural_cpm_play_basis,
        commercial_level=commercial_level,
        ad_repr_play=ad_repr_play,
        predicted_ad_play=predicted_ad_play,
        weighted_predicted_ad_play=weighted_predicted_ad_play,
        cpm_by_tier=cpm_by_tier,
        confidence_score=confidence,
        review_flag=review_flag,
        review_reasons=review_reasons,
        explanations=explanations,
        reference={"platform_expected_cpm": payload.platform_expected_cpm, "platform_expected_play": payload.platform_expected_play},
        debug={
            "valid_natural_plays": natural_plays,
            "ordered_natural_plays": natural_plays_ordered,
            "ordered_sponsored_plays": sponsored_plays_ordered,
            "ordered_overall_plays": overall_ordered,
            "valid_sponsored_plays": sponsored_plays,
            "activity_discount_factor": factor,
            "post_count_30d": effective_post_count,
            "post_count_30d_source": post_count_source,
            **chart_counts,
            "raw_primary_pool": raw_primary.model_dump(),
            "raw_secondary_pool": raw_secondary.model_dump() if raw_secondary else None,
            "raw_commercial_primary_pool": raw_commercial_primary.model_dump() if sponsored_plays else None,
            "raw_commercial_secondary_pool": raw_commercial_secondary.model_dump() if sponsored_plays and raw_commercial_secondary else None,
            "commercial_cpm_play_basis_source": commercial_play_basis_source,
            "config": config.model_dump(),
        },
        natural_trend_metrics=natural_trend_metrics,
        commercial_trend_metrics=commercial_trend_metrics,
        overall_trend_metrics=overall_trend_metrics,
        trend_metrics=natural_trend_metrics,
        commercial_ability=commercial_ability,
        base_predicted_play=base_predicted_play,
        final_prediction_factors=final_factors,
    )


def _clean_plays(values: list[int]) -> list[int]:
    return sorted(value for value in values if isinstance(value, int) and value > 0)


def _clean_plays_preserve_order(values: list[int]) -> list[int]:
    return [value for value in values if isinstance(value, int) and value > 0]


def _ordered_plays_from_points(points, fallback_values: list[int]) -> list[int]:
    if points:
        plays = [point.play for point in points if point.play and point.play > 0]
        if plays:
            return plays
    return _clean_plays_preserve_order(fallback_values)


def _overall_ordered_plays(payload: XingtuCpmInput) -> list[int]:
    dated: list[tuple[date, int]] = []
    for point in [*payload.personal_chart_points, *payload.star_chart_points]:
        parsed_date = _parse_chart_date(point.date)
        if parsed_date and point.play and point.play > 0:
            dated.append((parsed_date, point.play))
    if dated:
        return [play for _, play in sorted(dated, key=lambda item: item[0])]
    return [*_ordered_plays_from_points(payload.personal_chart_points, payload.natural_plays), *_ordered_plays_from_points(payload.star_chart_points, payload.sponsored_plays)]


def _effective_post_count(payload: XingtuCpmInput) -> tuple[int | None, str | None, dict[str, int | None]]:
    if payload.post_count_30d is not None:
        return payload.post_count_30d, payload.post_count_30d_source or "value_page", {
            "chart_date_count_30d_personal": payload.chart_date_count_30d_personal,
            "chart_date_count_30d_star": payload.chart_date_count_30d_star,
            "chart_date_count_30d_total": payload.chart_date_count_30d_total,
        }

    dated: list[tuple[str, date]] = []
    for kind, points in (("personal", payload.personal_chart_points), ("star", payload.star_chart_points)):
        for point in points:
            parsed_date = _parse_chart_date(point.date)
            if parsed_date and point.play and point.play > 0:
                dated.append((kind, parsed_date))
    if not dated:
        return None, None, {
            "chart_date_count_30d_personal": None,
            "chart_date_count_30d_star": None,
            "chart_date_count_30d_total": None,
        }
    latest = max(item[1] for item in dated)
    # The rule treats the latest visible chart date as the reference day.
    window_start = latest - timedelta(days=30)
    personal_count = sum(1 for kind, parsed_date in dated if kind == "personal" and window_start <= parsed_date <= latest)
    star_count = sum(1 for kind, parsed_date in dated if kind == "star" and window_start <= parsed_date <= latest)
    total = personal_count + star_count
    return total, "chart_dates", {
        "chart_date_count_30d_personal": personal_count,
        "chart_date_count_30d_star": star_count,
        "chart_date_count_30d_total": total,
    }


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


def _find_pools(values: list[int], config: XingtuCpmRuleConfig, points: list | None = None) -> tuple[PoolEstimate, PoolEstimate | None]:
    samples = _build_weighted_samples(values, points, config)
    if not samples:
        return PoolEstimate(explanation="没有有效自然播放量", source="insufficient_data"), None

    outlier_values = set(_high_outlier_values([sample.play for sample in samples], config))
    detection_samples = [sample for sample in samples if sample.play not in outlier_values]
    if len(detection_samples) < config.clustering.min_cluster_size:
        detection_samples = samples
        outlier_values = set()

    clusters = _cluster_weighted_samples(detection_samples, config)
    stable_clusters = [cluster for cluster in clusters if len(cluster) >= config.clustering.min_cluster_size]
    primary_cluster = stable_clusters[0] if stable_clusters else clusters[0]
    age_weighted = any(sample.parsed_date is not None for sample in samples)
    primary = _pool_from_samples(
        primary_cluster,
        config,
        "最低稳定簇作为初级流量池",
        source="observed_cluster",
        confidence=90.0 if stable_clusters else 72.0,
        sample_count=len(samples),
        outlier_count=len(outlier_values),
        age_weighted=age_weighted,
    )

    secondary_cluster = _select_secondary_cluster(stable_clusters, primary.center, config)
    if secondary_cluster:
        secondary = _pool_from_samples(
            secondary_cluster,
            config,
            "符合初级池倍数范围的稳定簇作为次级流量池",
            source="observed_cluster",
            confidence=86.0,
            sample_count=len(samples),
            outlier_count=len(outlier_values),
            age_weighted=age_weighted,
        )
    elif len(samples) >= config.min_valid_natural_plays and primary.center:
        secondary = _fallback_secondary_pool(detection_samples, primary.center, config, len(samples), len(outlier_values), age_weighted)
    else:
        secondary = None
    return primary, secondary


def _build_weighted_samples(values: list[int], points: list | None, config: XingtuCpmRuleConfig) -> list[_WeightedPlaySample]:
    dated: list[tuple[int, date | None]] = []
    if points:
        for point in points:
            play = getattr(point, "play", None)
            if isinstance(play, int) and play > 0:
                dated.append((play, _parse_chart_date(getattr(point, "date", None))))
    if not dated:
        dated = [(value, None) for value in values if isinstance(value, int) and value > 0]
    if not dated:
        return []

    dated_values = [item_date for _, item_date in dated if item_date is not None]
    reference_date = max(dated_values) if dated_values else None
    return [
        _WeightedPlaySample(play=play, parsed_date=parsed_date, weight=_time_decay_weight(parsed_date, reference_date, config))
        for play, parsed_date in dated
    ]


def _time_decay_weight(parsed_date: date | None, reference_date: date | None, config: XingtuCpmRuleConfig) -> float:
    if parsed_date is None or reference_date is None:
        return 1.0
    age_days = max(0, (reference_date - parsed_date).days)
    if age_days <= 90:
        return config.time_decay.days_90_weight
    if age_days <= 180:
        return config.time_decay.days_180_weight
    if age_days <= 365:
        return config.time_decay.days_365_weight
    return config.time_decay.older_weight


def _high_outlier_values(values: list[int], config: XingtuCpmRuleConfig) -> list[int]:
    cleaned = sorted(value for value in values if value > 0)
    if len(cleaned) < 4:
        return []
    q1 = _quantile(cleaned, 0.25)
    q3 = _quantile(cleaned, 0.75)
    iqr = max(0.0, q3 - q1)
    median_value = float(median(cleaned))
    iqr_limit = q3 + config.clustering.outlier_iqr_multiplier * iqr
    ratio_limit = median_value * config.clustering.outlier_max_to_median_ratio
    upper_limit = max(iqr_limit, ratio_limit)
    return [value for value in cleaned if value > upper_limit]


def _cluster_weighted_samples(samples: list[_WeightedPlaySample], config: XingtuCpmRuleConfig) -> list[list[_WeightedPlaySample]]:
    clusters: list[list[_WeightedPlaySample]] = []
    for sample in sorted(samples, key=lambda item: item.play):
        if not clusters:
            clusters.append([sample])
            continue
        cluster_center = _weighted_median(clusters[-1])
        if sample.play / max(1, cluster_center) <= config.clustering.adjacent_ratio_threshold:
            clusters[-1].append(sample)
        else:
            clusters.append([sample])
    return clusters


def _select_secondary_cluster(
    clusters: list[list[_WeightedPlaySample]],
    primary_center: int | None,
    config: XingtuCpmRuleConfig,
) -> list[_WeightedPlaySample] | None:
    if primary_center is None:
        return None
    for cluster in clusters:
        center = _weighted_median(cluster)
        if center <= primary_center:
            continue
        multiple = center / max(1, primary_center)
        if config.clustering.secondary_min_multiple <= multiple <= config.clustering.secondary_max_multiple:
            return cluster
    return None


def _fallback_secondary_pool(
    samples: list[_WeightedPlaySample],
    primary_center: int,
    config: XingtuCpmRuleConfig,
    sample_count: int,
    outlier_count: int,
    age_weighted: bool,
) -> PoolEstimate | None:
    upper_samples = [sample for sample in samples if sample.play > primary_center]
    if not upper_samples:
        return None
    sorted_samples = sorted(upper_samples, key=lambda item: item.play)
    low_value = _weighted_quantile(sorted_samples, config.clustering.secondary_quantile_low)
    high_value = _weighted_quantile(sorted_samples, config.clustering.secondary_quantile_high)
    band = [sample for sample in sorted_samples if low_value <= sample.play <= high_value]
    if len(band) < config.clustering.min_cluster_size:
        band = sorted_samples[-config.clustering.min_cluster_size :]
    return _pool_from_samples(
        band,
        config,
        "未发现独立稳定次级簇，使用上分位播放带估算次级流量池",
        source="quantile_fallback",
        confidence=58.0,
        sample_count=sample_count,
        outlier_count=outlier_count,
        age_weighted=age_weighted,
        is_estimated=True,
    )


def _pool_from_samples(
    samples: list[_WeightedPlaySample],
    config: XingtuCpmRuleConfig,
    explanation: str,
    source: str,
    confidence: float,
    sample_count: int,
    outlier_count: int,
    age_weighted: bool,
    is_estimated: bool = False,
) -> PoolEstimate:
    center = _weighted_median(samples)
    spread = config.clustering.primary_range_ratio
    cluster_values = sorted(sample.play for sample in samples)
    if len(cluster_values) >= 2:
        low = min(int(round(center * (1 - spread))), cluster_values[0])
        high = max(int(round(center * (1 + spread))), cluster_values[-1])
    else:
        low = int(round(center * (1 - spread)))
        high = int(round(center * (1 + spread)))
    return PoolEstimate(
        center=center,
        low=low,
        high=high,
        raw_center=center,
        adjustment_factor=1.0,
        cluster_values=cluster_values,
        explanation=explanation,
        source=source,
        confidence=confidence,
        sample_count=sample_count,
        weighted_sample_count=round(sum(sample.weight for sample in samples), 2),
        is_estimated=is_estimated,
        outlier_count=outlier_count,
        age_weighted=age_weighted,
    )


def _weighted_median(samples: list[_WeightedPlaySample]) -> int:
    return int(round(_weighted_quantile(samples, 0.5)))


def _weighted_quantile(samples: list[_WeightedPlaySample], quantile: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples, key=lambda item: item.play)
    total_weight = sum(max(0.0, sample.weight) for sample in ordered)
    if total_weight <= 0:
        return float(ordered[len(ordered) // 2].play)
    target = total_weight * quantile
    running = 0.0
    for sample in ordered:
        running += max(0.0, sample.weight)
        if running >= target:
            return float(sample.play)
    return float(ordered[-1].play)


def _quantile(values: list[int], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] * (1 - fraction) + ordered[upper_index] * fraction


def _post_discount_factor(post_count: int | None, config: XingtuCpmRuleConfig) -> float:
    if post_count is None:
        return 1.0
    if post_count >= 6:
        return config.post_count_discount_factors.get(6, 1.0)
    return config.post_count_discount_factors.get(post_count, 1.0)


def _apply_pool_discount(pool: PoolEstimate, factor: float) -> PoolEstimate:
    if not pool.center or factor <= 0:
        return pool
    return PoolEstimate(
        center=int(round(pool.center / factor)),
        low=int(round((pool.low or pool.center) / factor)),
        high=int(round((pool.high or pool.center) / factor)),
        raw_center=pool.center,
        adjustment_factor=factor,
        cluster_values=pool.cluster_values,
        explanation=f"{pool.explanation}；按发文活跃度 factor={factor} 折损",
        source=pool.source,
        confidence=pool.confidence,
        sample_count=pool.sample_count,
        weighted_sample_count=pool.weighted_sample_count,
        is_estimated=pool.is_estimated,
        outlier_count=pool.outlier_count,
        age_weighted=pool.age_weighted,
    )


def _ad_repr_play(ad_median: int | None, ad_mode: int | None, config: XingtuCpmRuleConfig) -> int | None:
    if ad_median is None and ad_mode is None:
        return None
    if ad_median is None:
        return ad_mode
    if ad_mode is None:
        return ad_median
    median_weight = config.ad_repr_median_weight
    return int(round(median_weight * ad_median + (1 - median_weight) * ad_mode))


def _predict_ad_play(ad_repr_play: int | None, primary: PoolEstimate, secondary: PoolEstimate | None) -> int | None:
    if ad_repr_play:
        return ad_repr_play
    if secondary and secondary.center:
        return int(round(secondary.center * 0.9))
    if primary.center:
        return int(round(primary.center * 0.8))
    return None


def _commercial_level(ad_repr_play: int | None, primary: PoolEstimate, secondary: PoolEstimate | None) -> str:
    if ad_repr_play is None or primary.center is None:
        return "D"
    if secondary and secondary.high and ad_repr_play >= secondary.high:
        return "S"
    if secondary and secondary.low and ad_repr_play >= secondary.low:
        return "A"
    if primary.high and ad_repr_play > primary.high:
        return "B"
    if primary.low and ad_repr_play >= primary.low:
        return "C"
    return "D"


def _prices(payload: XingtuCpmInput) -> dict[str, float | None]:
    return {
        "20s": payload.price_20s,
        "20-60s": payload.price_20_60s,
        "60s+": payload.price_60s_plus,
    }


def _commercial_cpm_play_basis(commercial_primary: PoolEstimate | None, commercial_secondary: PoolEstimate | None, ad_repr_play: int | None) -> tuple[int | None, str | None]:
    if commercial_primary and commercial_primary.center:
        return commercial_primary.center, "star_chart_primary_pool"
    if commercial_secondary and commercial_secondary.center:
        return commercial_secondary.center, "star_chart_secondary_pool"
    if ad_repr_play:
        return ad_repr_play, "ad_repr_fallback"
    return None, None


def _commercial_level_from_commercial_pool(commercial_center: int | None, primary: PoolEstimate, secondary: PoolEstimate | None) -> str:
    if commercial_center is None or primary.center is None:
        return "D"
    if secondary and secondary.high and commercial_center >= secondary.high:
        return "S"
    if secondary and secondary.low and commercial_center >= secondary.low:
        return "A"
    if primary.high and commercial_center > primary.high:
        return "B"
    if primary.low and commercial_center >= primary.low:
        return "C"
    return "D"


def _check_chart_summary(summary_avg: int | None, values: list[int], label: str, review_reasons: list[str], config: XingtuCpmRuleConfig) -> None:
    if summary_avg is None or not values:
        return
    calculated = int(round(sum(values) / len(values)))
    ratio = max(summary_avg, calculated) / max(1, min(summary_avg, calculated))
    if ratio > config.ad_stat_divergence_ratio:
        review_reasons.append(f"{label}与数组均值差异过大")


def _calculate_cpms(payload: XingtuCpmInput, commercial_center: int | None, natural_center: int | None, commercial_source: str | None) -> dict[str, CpmTierResult]:
    results: dict[str, CpmTierResult] = {}
    for tier, price in _prices(payload).items():
        if price is None:
            results[tier] = CpmTierResult(reason="缺少报价")
            continue
        predicted_cpm = price / commercial_center * 1000 if commercial_center else None
        natural_cpm = price / natural_center * 1000 if natural_center else None
        results[tier] = CpmTierResult(
            price=price,
            predicted_cpm=round(predicted_cpm, 2) if predicted_cpm is not None else None,
            natural_cpm=round(natural_cpm, 2) if natural_cpm is not None else None,
            reason=None if predicted_cpm is not None and natural_cpm is not None else "缺少播放量基准",
            commercial_cpm_play_basis_source=commercial_source,
            natural_cpm_play_basis_source="natural_primary_pool" if natural_center else None,
        )
    return results


def _build_explanations(
    primary: PoolEstimate,
    secondary: PoolEstimate | None,
    ad_repr_play: int | None,
    predicted_ad_play: int | None,
    factor: float,
) -> list[str]:
    items = [primary.explanation]
    if secondary:
        items.append(secondary.explanation)
    else:
        items.append("未识别到次级流量池，按单池账号降级处理。")
    if factor != 1:
        items.append(f"近30天发文不足，活跃度风险 factor={factor}；单条播放量池不做折损。")
    if ad_repr_play:
        items.append(f"商单代表值采用中位数/分桶众数组合，得到 {ad_repr_play}。")
    if predicted_ad_play:
        items.append(f"预估商单播放量为 {predicted_ad_play}。")
    return items


def _assess_commercial_quality_ability(
    sponsored_plays: list[int],
    primary: PoolEstimate,
    secondary: PoolEstimate | None,
    config: XingtuCpmRuleConfig,
) -> CommercialAbilityMetrics:
    """评估达人商单制作能力。"""
    wp_config = config.weighted_prediction

    if not sponsored_plays or not primary.center:
        return CommercialAbilityMetrics(
            ability_score=0.5,
            ability_level="unknown",
            coefficient=1.0,
            explanation="缺少商单数据，使用默认能力系数",
        )

    ad_median = int(round(median(sponsored_plays)))
    ad_mode_val = bucketed_mode(sponsored_plays, config) or ad_median
    ad_repr = _ad_repr_play(ad_median, ad_mode_val, config)

    primary_center = primary.center
    secondary_high = secondary.high if secondary and secondary.high else primary_center * 3
    secondary_center = secondary.center if secondary and secondary.center else primary_center * 2.5
    secondary_low = secondary.low if secondary and secondary.low else primary_center * 2

    ability_score = 0.5
    ability_level = "normal"
    coefficient = 1.0
    position = ""

    if ad_repr >= secondary_high * 0.9:
        ability_score = 0.9
        ability_level = "premium"
        coefficient = wp_config.commercial_coefficient_max
        position = "商单位于次级池高位，属于精品制作"
    elif ad_repr >= secondary_center:
        ability_score = 0.75
        ability_level = "good"
        coefficient = 1.1
        position = "商单位于次级池中位，属于良好制作"
    elif ad_repr >= secondary_low:
        ability_score = 0.6
        ability_level = "above_normal"
        coefficient = 1.0
        position = "商单位于次级池低位"
    elif ad_repr >= primary_center:
        ability_score = 0.45
        ability_level = "normal"
        coefficient = 0.9
        position = "商单位于初级池范围"
    elif ad_repr >= primary_center * 0.8:
        ability_score = 0.3
        ability_level = "below_normal"
        coefficient = 0.75
        position = "商单略低于初级池"
    else:
        ability_score = 0.15
        ability_level = "poor"
        coefficient = wp_config.commercial_coefficient_min
        position = "商单远低于初级池"

    return CommercialAbilityMetrics(
        ability_score=ability_score,
        ability_level=ability_level,
        coefficient=coefficient,
        explanation=position,
        historical_commercial_position=position,
    )


def _analyze_traffic_trend(
    natural_plays: list[int],
    config: XingtuCpmRuleConfig,
) -> TrendMetrics:
    """分析流量趋势。"""
    wp_config = config.weighted_prediction

    if len(natural_plays) < 4:
        return TrendMetrics(
            trend_coefficient=1.0,
            trend_direction="insufficient_data",
        )

    mid = len(natural_plays) // 2
    first_half = natural_plays[:mid]
    second_half = natural_plays[mid:]

    first_median = int(round(median(first_half)))
    second_median = int(round(median(second_half)))

    if first_median == 0:
        trend_coeff = 1.0
    else:
        trend_coeff = second_median / first_median

    trend_coeff = max(wp_config.trend_min_coefficient, min(wp_config.trend_max_coefficient, trend_coeff))

    if trend_coeff > 1.05:
        direction = "rising"
    elif trend_coeff < 0.95:
        direction = "falling"
    else:
        direction = "stable"

    return TrendMetrics(
        trend_coefficient=trend_coeff,
        trend_direction=direction,
        first_half_median=first_median,
        second_half_median=second_median,
    )


def _calculate_base_predicted_play(
    commercial_ability: CommercialAbilityMetrics,
    primary: PoolEstimate,
    secondary: PoolEstimate | None,
    commercial_primary: PoolEstimate | None,
    commercial_secondary: PoolEstimate | None,
    ad_repr_play: int | None,
) -> Tuple[int | None, str]:
    """基础预测优先使用星图视频池；自然池只作为对照，不再作为默认来源。"""
    if commercial_primary and commercial_primary.center:
        return commercial_primary.center, "star_chart_primary_pool"
    if commercial_secondary and commercial_secondary.center:
        return commercial_secondary.center, "star_chart_secondary_pool"
    if ad_repr_play:
        return ad_repr_play, "ad_repr_fallback"
    if primary.center:
        return primary.center, "natural_primary_reference_fallback"
    return None, "no_play_basis"


def _predict_ad_play_weighted(
    sponsored_plays: list[int],
    primary: PoolEstimate,
    secondary: PoolEstimate | None,
    commercial_primary: PoolEstimate | None,
    commercial_secondary: PoolEstimate | None,
    ad_repr_play: int | None,
    trend_metrics: TrendMetrics,
    config: XingtuCpmRuleConfig,
) -> Tuple[int | None, CommercialAbilityMetrics, int | None, dict[str, float]]:
    """加权预估商单播放量的新算法。"""
    commercial_ability = _assess_commercial_quality_ability(sponsored_plays, primary, secondary, config)
    engagement_coeff = config.weighted_prediction.engagement_coefficient

    base_play, base_source = _calculate_base_predicted_play(commercial_ability, primary, secondary, commercial_primary, commercial_secondary, ad_repr_play)

    if base_play is None:
        return None, commercial_ability, None, {}

    factors = {
        "commercial_ability": commercial_ability.coefficient,
        "overall_trend": trend_metrics.trend_coefficient,
        "engagement": engagement_coeff,
    }

    final_play = base_play
    final_play = int(round(final_play * commercial_ability.coefficient))
    final_play = int(round(final_play * trend_metrics.trend_coefficient))
    final_play = int(round(final_play * engagement_coeff))

    return final_play, commercial_ability, base_play, factors
