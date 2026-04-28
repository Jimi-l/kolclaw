from __future__ import annotations

from app.schemas.shortlist import ShortlistCandidate, ShortlistRequirement, ShortlistScoreBreakdown
from app.schemas.xingtu import XingtuCreatorDetail
from app.utils.normalization import clamp, contains_keywords, inverse_scale_between, overlap_score, scale_between, unique_list


def rank_shortlist_candidates(
    requirement: ShortlistRequirement,
    creators: list[XingtuCreatorDetail],
    shortlist_limit: int = 5,
) -> tuple[list[ShortlistCandidate], dict[str, int]]:
    ranked: list[ShortlistCandidate] = []
    filtered_out_reasons: dict[str, int] = {}

    for creator in creators:
        should_include, hard_fail_reason = _passes_v1_gate(creator, requirement)
        if not should_include:
            filtered_out_reasons[hard_fail_reason] = filtered_out_reasons.get(hard_fail_reason, 0) + 1
            continue

        breakdown, reason, recommendation_level, risk_flags = _score_creator(creator, requirement)
        ranked.append(
            ShortlistCandidate(
                creator=creator,
                score_breakdown=breakdown,
                recommendation_reason=reason,
                recommendation_level=recommendation_level,
                risk_flags=risk_flags,
            )
        )

    ranked.sort(key=lambda item: item.score_breakdown.total_score, reverse=True)
    return ranked[:shortlist_limit], filtered_out_reasons


def _passes_v1_gate(creator: XingtuCreatorDetail, requirement: ShortlistRequirement) -> tuple[bool, str]:
    profile_text = _profile_text(creator)
    exclusions = requirement.exclusions or requirement.hard_constraints.exclusions
    if exclusions and contains_keywords(profile_text, exclusions) > 0:
        return False, "exclusion_keyword_hit"

    budget_cap = requirement.hard_constraints.budget_cap_per_creator
    price = creator.price or creator.settlement_price_est
    if budget_cap is not None and price is not None and price > budget_cap * 2.0:
        return False, "price_above_v1_cap"

    min_fans = requirement.hard_constraints.min_fans_count
    if min_fans is not None and creator.fans_count is not None and creator.fans_count < min_fans * 0.45:
        return False, "fans_far_below_requirement"

    return True, ""


def _score_creator(
    creator: XingtuCreatorDetail,
    requirement: ShortlistRequirement,
) -> tuple[ShortlistScoreBreakdown, str, str, list[str]]:
    profile_text = _profile_text(creator)
    creator_categories = creator.creator_types + creator.experience_tags
    required_categories = unique_list(
        [
            *(requirement.hard_constraints.creator_categories or []),
            *(requirement.preferred_constraints.creator_categories or []),
            requirement.product_category or "",
        ]
    )
    keyword_bundle = unique_list(
        [
            *(requirement.keywords or []),
            *(requirement.content_style_tags or []),
            *(requirement.tone_tags or []),
        ]
    )

    category_overlap = overlap_score(creator_categories, required_categories)
    keyword_fit = contains_keywords(profile_text, keyword_bundle)
    city_fit = 1.0 if requirement.city and creator.city and creator.city.lower() == requirement.city.lower() else 0.45
    budget_fit = _budget_fit(creator, requirement)
    brief_match = clamp(100 * (0.45 * category_overlap + 0.25 * keyword_fit + 0.15 * city_fit + 0.15 * budget_fit))

    female_target = any(tag in requirement.target_audience for tag in ("女性", "都市白领", "精致消费人群"))
    female_signal = creator.female_ratio if creator.female_ratio is not None else (0.6 if female_target else 0.5)
    deep_user_ratio = _safe_ratio(creator.monthly_deep_users, creator.fans_count)
    connected_user_ratio = _safe_ratio(creator.monthly_connected_users, creator.fans_count)
    audience_match = clamp(
        100
        * (
            0.45 * (female_signal if female_target else max(female_signal, 0.5))
            + 0.3 * scale_between(deep_user_ratio, 0.8, 6.0)
            + 0.25 * scale_between(connected_user_ratio, 1.5, 18.0)
        )
    )

    content_fit = clamp(
        100
        * (
            0.55 * keyword_fit
            + 0.45 * overlap_score(creator_categories, requirement.content_style_tags + requirement.tone_tags)
        )
    )

    quality_activity = clamp(
        100
        * (
            0.3 * scale_between(float(creator.avg_video_play_median or 0), 80000, 3000000)
            + 0.2 * scale_between(float(creator.fans_count or 0), 50000, 2500000)
            + 0.2 * scale_between(float(creator.monthly_growth_rate or 0), 0.0, 0.08)
            + 0.15 * scale_between(float(creator.average_completion_rate or 0), 0.03, 0.22)
            + 0.15 * scale_between(float(creator.average_interaction_rate or 0), 0.01, 0.08)
        )
    )

    play_per_price = (
        float(creator.avg_video_play_median or creator.median_commercial_play or 0)
        / max(float(creator.price or creator.settlement_price_est or 1), 1.0)
    )
    commercial_signal = clamp(
        100
        * (
            0.35 * _budget_fit(creator, requirement)
            + 0.35 * scale_between(play_per_price, 12.0, 120.0)
            + 0.3 * inverse_scale_between(float(creator.expected_cpm or creator.natural_cpm or 120.0), 20.0, 120.0)
        )
    )

    risk_flags: list[str] = []
    risk_penalty = 0.0
    if creator.fans_count is None:
        risk_flags.append("粉丝数缺失")
        risk_penalty += 10
    if creator.avg_video_play_median is None:
        risk_flags.append("播放中位数缺失")
        risk_penalty += 10
    if creator.monthly_growth_rate is not None and creator.monthly_growth_rate < 0.01:
        risk_flags.append("近30天涨粉偏弱")
        risk_penalty += 8
    if budget_fit < 0.45:
        risk_flags.append("价格接近或高于V1预算阈值")
        risk_penalty += 10
    if requirement.city and creator.city and creator.city.lower() != requirement.city.lower():
        risk_flags.append("非目标城市达人")
        risk_penalty += 5

    total_score = clamp(
        0.25 * brief_match
        + 0.2 * audience_match
        + 0.2 * content_fit
        + 0.2 * quality_activity
        + 0.15 * commercial_signal
        - risk_penalty
    )

    reasons: list[str] = []
    if category_overlap >= 0.5:
        reasons.append("Creator tags overlap strongly with the requested category.")
    if keyword_fit >= 0.4:
        reasons.append("Profile tags reflect the requested content style and tone.")
    if audience_match >= 65:
        reasons.append("Audience signals align with the target crowd in the brief.")
    if quality_activity >= 65:
        reasons.append("Play/activity signals are strong enough for a first shortlist.")
    if commercial_signal >= 60:
        reasons.append("Commercial efficiency looks workable for the current budget.")
    if not reasons:
        reasons.append("Baseline fit is workable, but this profile still needs manual review.")

    breakdown = ShortlistScoreBreakdown(
        brief_match=round(brief_match, 2),
        audience_match=round(audience_match, 2),
        content_fit=round(content_fit, 2),
        quality_activity=round(quality_activity, 2),
        commercial_signal=round(commercial_signal, 2),
        risk_penalty=round(risk_penalty, 2),
        total_score=round(total_score, 2),
        explanation=unique_list(
            reasons
            + [
                f"Budget fit: {budget_fit:.0%}.",
                f"Play median: {(creator.avg_video_play_median or 0):,.0f}.",
                f"Monthly growth: {(creator.monthly_growth_rate or 0):.1%}.",
            ]
        ),
    )

    recommendation_reason = " ".join(reasons)
    recommendation_level = _recommendation_level(total_score)
    return breakdown, recommendation_reason, recommendation_level, unique_list(risk_flags)


def _profile_text(creator: XingtuCreatorDetail) -> str:
    return " ".join(
        unique_list(
            [
                creator.creator_name or "",
                *(creator.creator_types or []),
                *(creator.experience_tags or []),
                creator.recent_content_summary or "",
                creator.recent_curve_summary or "",
            ]
        )
    )


def _budget_fit(creator: XingtuCreatorDetail, requirement: ShortlistRequirement) -> float:
    budget_cap = requirement.hard_constraints.budget_cap_per_creator
    if budget_cap is None:
        return 0.7
    price = float(creator.price or creator.settlement_price_est or 0.0)
    if price <= 0:
        return 0.55
    return inverse_scale_between(price, budget_cap * 0.45, budget_cap * 1.2)


def _safe_ratio(numerator: int | None, denominator: int | None) -> float:
    if numerator is None or denominator in (None, 0):
        return 0.0
    return numerator / denominator


def _recommendation_level(score: float) -> str:
    if score >= 78:
        return "Priority"
    if score >= 64:
        return "Recommended"
    if score >= 50:
        return "Review"
    return "Watch"
