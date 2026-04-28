from __future__ import annotations

from app.schemas.brief import CampaignBrief
from app.schemas.candidate import CandidateCreator
from app.schemas.scoring import ScoreBreakdown
from app.schemas.strategy_template import StrategyTemplate
from app.utils.normalization import (
    clamp,
    contains_keywords,
    inverse_scale_between,
    overlap_score,
    scale_between,
    unique_list,
)


def score_candidate(candidate: CandidateCreator, brief: CampaignBrief, template: StrategyTemplate, max_candidate_price: float | None) -> tuple[ScoreBreakdown, str, list[str], str]:
    type_overlap = overlap_score(candidate.creator_types, brief.creator_types)
    experience_overlap = overlap_score(candidate.experience_tags, [*brief.content_tags, *brief.style_tags, *brief.keywords])
    city_fit = 1.0 if (candidate.city or "").lower() == brief.city.lower() else 0.25
    keyword_fit = contains_keywords(candidate.recent_content_summary, [*brief.content_tags, *brief.style_tags, *brief.keywords])
    brief_match = clamp(100 * (0.4 * type_overlap + 0.25 * experience_overlap + 0.2 * city_fit + 0.15 * keyword_fit))

    content_overlap = overlap_score(candidate.content_tags, brief.content_tags)
    style_overlap = overlap_score(candidate.style_tags, brief.style_tags)
    template_overlap = overlap_score(candidate.content_tags, template.soft_preferences.preferred_content_tags)
    content_fit = clamp(100 * (0.4 * content_overlap + 0.25 * style_overlap + 0.2 * template_overlap + 0.15 * keyword_fit))

    audience_fit = clamp(
        100
        * (
            0.45 * candidate.female_ratio
            + 0.35 * candidate.core_female_ratio
            + 0.2 * candidate.deep_fan_ratio
        )
    )

    play_efficiency = scale_between(candidate.median_commercial_play / max(candidate.settlement_price_est, 1.0), 1.2, 5.5)
    cpm_efficiency = inverse_scale_between(candidate.natural_cpm, 18.0, 90.0)
    cpe_efficiency = inverse_scale_between(candidate.cpe, 0.8, 6.0)
    completion_efficiency = (
        0.65 * candidate.commercial_completion_rate
        + 0.35 * inverse_scale_between(candidate.completion_cpm, 18.0, 120.0)
    )
    price_fit = 1.0
    if max_candidate_price:
        price_fit = inverse_scale_between(candidate.settlement_price_est, max_candidate_price * 0.55, max_candidate_price * 1.1)

    commercial_efficiency = clamp(
        100
        * (
            0.3 * play_efficiency
            + 0.2 * cpm_efficiency
            + 0.2 * cpe_efficiency
            + 0.2 * completion_efficiency
            + 0.1 * price_fit
        )
    )

    curve_signal = contains_keywords(candidate.recent_curve_summary, ["steady", "rising", "breakout", "upward", "accelerating"])
    growth_signal = clamp(
        100
        * (
            0.45 * scale_between(candidate.monthly_growth_rate, -0.03, 0.14)
            + 0.25 * curve_signal
            + 0.15 * candidate.broad_fan_ratio
            + 0.15 * candidate.deep_fan_ratio
        )
    )

    weights = template.score_weights
    weighted_total = clamp(
        (
            brief_match * weights.brief_match
            + content_fit * weights.content_fit
            + commercial_efficiency * weights.commercial_efficiency
            + audience_fit * weights.audience_fit
            + growth_signal * weights.growth_signal
        )
        / (weights.brief_match + weights.content_fit + weights.commercial_efficiency + weights.audience_fit + weights.growth_signal)
    )

    explanation = [
        f"Type overlap score: {type_overlap:.0%}.",
        f"Content/style fit score: {(content_overlap + style_overlap) / 2:.0%}.",
        f"Audience female ratio: {candidate.female_ratio:.0%}.",
        f"Settlement estimate: {candidate.settlement_price_est:,.0f}.",
        f"Monthly growth rate: {candidate.monthly_growth_rate:.1%}.",
    ]

    breakdown = ScoreBreakdown(
        brief_match=round(brief_match, 2),
        content_fit=round(content_fit, 2),
        audience_fit=round(audience_fit, 2),
        commercial_efficiency=round(commercial_efficiency, 2),
        growth_signal=round(growth_signal, 2),
        weighted_total=round(weighted_total, 2),
        explanation=explanation,
    )

    reasons = []
    matched_types = sorted(set(candidate.creator_types) & set(brief.creator_types))
    if matched_types:
        reasons.append(f"Matches creator types: {', '.join(matched_types)}")
    if (candidate.city or "").lower() == brief.city.lower():
        reasons.append(f"Shanghai-local profile supports offline activation")
    if content_fit >= 70:
        reasons.append("Recent content aligns with outfit/show-style execution")
    if commercial_efficiency >= 70:
        reasons.append("Commercial metrics are efficient for the configured budget")
    if growth_signal >= 65:
        reasons.append("Recent growth trend is healthy")

    risk_notes = list(candidate.risk_notes)
    if candidate.monthly_growth_rate < 0.02:
        risk_notes.append("Growth signal is soft and should be reviewed manually.")
    if candidate.female_ratio < max(template.hard_filters.min_female_ratio or 0.0, 0.6):
        risk_notes.append("Audience fit is acceptable but not especially female-skewed for this brief.")
    if max_candidate_price and candidate.settlement_price_est > max_candidate_price * 0.9:
        risk_notes.append("Pricing sits near the configured cap.")
    if (candidate.city or "").lower() != brief.city.lower():
        risk_notes.append("Non-local creator may require logistics confirmation for the offline show.")
    risk_notes = unique_list(risk_notes)

    recommendation_level = recommendation_from_score(weighted_total)
    reason_text = ". ".join(reasons) if reasons else "Solid baseline fit with room for manual review."

    return breakdown, reason_text, risk_notes, recommendation_level


def recommendation_from_score(score: float) -> str:
    if score >= 80:
        return "Priority"
    if score >= 68:
        return "Recommended"
    if score >= 55:
        return "Consider"
    return "Watch"
