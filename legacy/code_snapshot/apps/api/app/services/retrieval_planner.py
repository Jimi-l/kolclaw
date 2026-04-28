from __future__ import annotations

from app.schemas.brief import CampaignBrief
from app.schemas.pipeline import RetrievalPlan
from app.schemas.strategy_template import StrategyTemplate
from app.utils.normalization import unique_list


def build_retrieval_plan(brief: CampaignBrief, template: StrategyTemplate) -> RetrievalPlan:
    max_candidate_price = template.hard_filters.max_candidate_price
    if template.hard_filters.max_price_share_of_budget is not None:
        share_cap = brief.budget_total * template.hard_filters.max_price_share_of_budget
        max_candidate_price = min(max_candidate_price, share_cap) if max_candidate_price else share_cap
    if brief.constraints.max_candidate_price:
        max_candidate_price = min(max_candidate_price, brief.constraints.max_candidate_price) if max_candidate_price else brief.constraints.max_candidate_price

    selected_filters = {
        "platform": brief.platform,
        "min_fans_count": max(template.hard_filters.min_fans_count or 0, brief.constraints.min_fans_count or 0),
        "min_female_ratio": max(template.hard_filters.min_female_ratio or 0.0, brief.constraints.min_female_ratio or 0.0),
        "max_candidate_price": round(max_candidate_price, 2) if max_candidate_price is not None else None,
        "creator_type_overlap_required": template.hard_filters.require_creator_type_overlap,
        "target_city": brief.city,
    }

    hard_filter_summary = [
        f"Platform locked to {brief.platform}.",
        f"Fans floor set to {selected_filters['min_fans_count']:,}.",
        f"Female ratio floor set to {selected_filters['min_female_ratio']:.0%}.",
        f"Per-creator settlement cap set to {selected_filters['max_candidate_price'] or 'none'}.",
        "Creator type overlap is required." if template.hard_filters.require_creator_type_overlap else "Creator type overlap is optional.",
    ]

    generated_keywords = unique_list(
        [
            brief.campaign_name,
            brief.city,
            *brief.keywords,
            *brief.content_tags,
            *brief.style_tags,
            *template.soft_preferences.preferred_content_tags,
            *template.soft_preferences.preferred_style_tags,
        ]
    )

    ordered_weights = sorted(template.score_weights.model_dump().items(), key=lambda item: item[1], reverse=True)
    ranking_priorities = [f"{name} ({weight:.0%})" for name, weight in ordered_weights if weight > 0]

    return RetrievalPlan(
        selected_filters=selected_filters,
        generated_keywords=generated_keywords,
        hard_filter_summary=hard_filter_summary,
        ranking_priorities=ranking_priorities,
    )
