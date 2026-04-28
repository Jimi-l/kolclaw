from __future__ import annotations

from collections import Counter

from app.schemas.brief import CampaignBrief
from app.schemas.candidate import CandidateCreator
from app.schemas.strategy_template import StrategyTemplate
from app.services.scoring_engine import score_candidate
from app.utils.normalization import normalize_text


def rank_candidates(
    candidates: list[CandidateCreator],
    brief: CampaignBrief,
    template: StrategyTemplate,
    limit: int = 20,
) -> tuple[list[CandidateCreator], dict[str, int], int]:
    filter_reasons: Counter[str] = Counter()
    ranked: list[CandidateCreator] = []

    max_candidate_price = template.hard_filters.max_candidate_price
    if template.hard_filters.max_price_share_of_budget is not None:
        share_cap = brief.budget_total * template.hard_filters.max_price_share_of_budget
        max_candidate_price = min(max_candidate_price, share_cap) if max_candidate_price else share_cap
    if brief.constraints.max_candidate_price:
        max_candidate_price = min(max_candidate_price, brief.constraints.max_candidate_price) if max_candidate_price else brief.constraints.max_candidate_price

    min_fans = max(template.hard_filters.min_fans_count or 0, brief.constraints.min_fans_count or 0)
    min_female_ratio = max(template.hard_filters.min_female_ratio or 0.0, brief.constraints.min_female_ratio or 0.0)
    expected_platforms = _supported_platforms(brief.platform, template)

    for candidate in candidates:
        if template.hard_filters.platform_match and normalize_text(candidate.platform) not in expected_platforms:
            filter_reasons["platform_mismatch"] += 1
            continue
        if candidate.fans_count < min_fans:
            filter_reasons["fans_below_threshold"] += 1
            continue
        if candidate.female_ratio < min_female_ratio:
            filter_reasons["female_ratio_below_threshold"] += 1
            continue
        if max_candidate_price is not None and candidate.settlement_price_est > max_candidate_price:
            filter_reasons["over_budget"] += 1
            continue
        if template.hard_filters.require_creator_type_overlap and not (set(candidate.creator_types) & set(brief.creator_types)):
            filter_reasons["creator_type_mismatch"] += 1
            continue

        breakdown, reason, risk_notes, recommendation_level = score_candidate(candidate, brief, template, max_candidate_price)
        ranked.append(
            candidate.model_copy(
                update={
                    "score_breakdown": breakdown,
                    "final_score": breakdown.weighted_total,
                    "recommendation_reason": reason,
                    "risk_notes": risk_notes,
                    "recommendation_level": recommendation_level,
                }
            )
        )

    ranked.sort(key=lambda item: item.final_score, reverse=True)
    passed_count = len(ranked)
    return ranked[:limit], dict(filter_reasons), passed_count


def _supported_platforms(brief_platform: str, template: StrategyTemplate) -> set[str]:
    supported = {normalize_text(brief_platform)}
    for alias in template.platform_mapping.get(brief_platform, []):
        supported.add(normalize_text(alias))
    return supported
