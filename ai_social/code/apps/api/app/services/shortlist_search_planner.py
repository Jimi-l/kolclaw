from __future__ import annotations

from app.schemas.shortlist import ShortlistRequirement, ShortlistSearchPlan
from app.schemas.xingtu import XingtuFilterConfig
from app.utils.normalization import unique_list

SAFE_CATEGORY_TO_FILTER = {
    "美妆": ("美妆", ["美妆测评种草"]),
}


def build_shortlist_search_plan(
    requirement: ShortlistRequirement,
    collection_limit: int = 8,
    shortlist_limit: int = 5,
) -> ShortlistSearchPlan:
    generated_keywords = unique_list(
        [
            requirement.brand or "",
            requirement.product_name or "",
            requirement.product_sku or "",
            requirement.product_category or "",
            *(requirement.preferred_constraints.content_themes or []),
            *(requirement.tone_tags or []),
            *(requirement.target_audience or []),
        ]
    )

    named_filters: dict[str, list[str]] = {}
    search_notes: list[str] = []
    unapplied_constraints: list[str] = []

    if requirement.product_category in SAFE_CATEGORY_TO_FILTER:
        filter_name, values = SAFE_CATEGORY_TO_FILTER[requirement.product_category]
        named_filters[filter_name] = list(values)
        search_notes.append(
            f"Applied hardened Xingtu dropdown mapping `{filter_name} -> {', '.join(values)}`."
        )
    else:
        unapplied_constraints.append(
            "No hardened Xingtu dropdown mapping exists yet for this primary category; ranking carries more of the fit logic."
        )

    if requirement.city:
        unapplied_constraints.append(
            f"City preference `{requirement.city}` is currently enforced in scoring rather than live Xingtu filters."
        )

    if requirement.hard_constraints.min_fans_count is not None:
        unapplied_constraints.append(
            f"Minimum fans `{requirement.hard_constraints.min_fans_count:,}` is enforced post-collection in V1."
        )

    if requirement.hard_constraints.budget_cap_per_creator is not None:
        unapplied_constraints.append(
            f"Per-creator budget cap `{requirement.hard_constraints.budget_cap_per_creator:,.0f}` is enforced during scoring and shortlist filtering."
        )

    filter_config = XingtuFilterConfig(named_filters=named_filters)

    hard_filter_summary = [
        f"Platform: {requirement.platform}",
        f"Primary creator category: {requirement.product_category or 'unspecified'}",
        f"Hard exclusions: {', '.join(requirement.exclusions) if requirement.exclusions else 'none'}",
    ]

    ranking_priorities = [
        "Match creator category and brief keywords",
        "Prefer audience fit for the stated target audience",
        "Prioritize stable play volume, activity, and completion quality",
        "Reward efficient commercial indicators when available",
        "Apply risk penalties for exclusions, missing data, and pricing mismatch",
    ]

    return ShortlistSearchPlan(
        platform=requirement.platform,
        filter_config=filter_config,
        generated_keywords=generated_keywords,
        hard_filter_summary=hard_filter_summary,
        ranking_priorities=ranking_priorities,
        search_notes=search_notes,
        unapplied_constraints=unapplied_constraints,
        collection_limit=collection_limit,
        shortlist_limit=shortlist_limit,
    )
