from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.shortlist import ShortlistPlanRequest  # noqa: E402
from app.schemas.xingtu import XingtuCreatorDetail  # noqa: E402
from app.services.reference_docs_loader import ReferenceDocsLoader  # noqa: E402
from app.services.shortlist_brief_parser import parse_shortlist_brief  # noqa: E402
from app.services.shortlist_runner import ShortlistRunner  # noqa: E402
from app.services.shortlist_scoring import rank_shortlist_candidates  # noqa: E402
from app.services.shortlist_search_planner import build_shortlist_search_plan  # noqa: E402


class ShortlistV1UnitTests(unittest.TestCase):
    def test_parse_shortlist_brief_extracts_requirement_buckets(self) -> None:
        raw_text = """
Brand: Luminelle
Product: Velvet Lip Glaze
SKU: V06
Platform: douyin
City: shanghai
Budget: 80000 RMB
Target audience: female office workers, beauty shoppers
KPI: stable views, completion rate, cost efficiency
Style: polished beauty tutorial, seeding
Tone: premium, trustworthy
Avoid: parenting, pets
Must: beauty creators with female audience
Prefer: shanghai-based creators with recent growth
Notes: shortlist five creators for the first review
"""

        requirement, parser_notes = parse_shortlist_brief(raw_text)

        self.assertEqual(requirement.brand, "Luminelle")
        self.assertEqual(requirement.product_name, "Velvet Lip Glaze")
        self.assertEqual(requirement.product_sku, "V06")
        self.assertEqual(requirement.product_category, "美妆")
        self.assertEqual(requirement.city, "shanghai")
        self.assertEqual(requirement.budget_total, 80000)
        self.assertIn("女性", requirement.target_audience)
        self.assertIn("美妆", requirement.hard_constraints.creator_categories)
        self.assertIn("parenting", requirement.exclusions)
        self.assertTrue(parser_notes)

    def test_search_plan_maps_beauty_brief_to_hardened_filter(self) -> None:
        requirement, _ = parse_shortlist_brief(
            "Brand: Luminelle\nProduct: Velvet Lip Glaze\nBudget: 80000 RMB\nbeauty seeding brief for female audience"
        )

        plan = build_shortlist_search_plan(requirement, collection_limit=6, shortlist_limit=4)

        self.assertEqual(plan.filter_config.named_filters["美妆"], ["美妆测评种草"])
        self.assertEqual(plan.collection_limit, 6)
        self.assertEqual(plan.shortlist_limit, 4)

    def test_reference_docs_loader_returns_operational_v1_docs(self) -> None:
        loader = ReferenceDocsLoader()
        references = loader.list_v1_operational_references()

        titles = {item.title for item in references}
        self.assertIn("选号prompt", titles)
        self.assertIn("AI智能巡号_星图数据补充_执行提示词", titles)

    def test_shortlist_scoring_prefers_stronger_beauty_profile(self) -> None:
        requirement, _ = parse_shortlist_brief(
            "Brand: Luminelle\nProduct: Velvet Lip Glaze\nBudget: 80000 RMB\nbeauty seeding brief for female audience in shanghai"
        )

        strong = XingtuCreatorDetail(
            creator_name="Demo Beauty Creator",
            creator_id="1",
            creator_types=["美妆", "明星妆容", "种草"],
            city="shanghai",
            fans_count=2571000,
            female_ratio=0.82,
            price=50000,
            avg_video_play_median=4602000,
            expected_cpm=51,
            average_completion_rate=0.095,
            average_interaction_rate=0.048,
            monthly_growth_rate=0.0362,
            monthly_connected_users=62558000,
            monthly_deep_users=21758000,
        )
        weak = XingtuCreatorDetail(
            creator_name="Other Creator",
            creator_id="2",
            creator_types=["宠物", "搞笑"],
            city="beijing",
            fans_count=90000,
            female_ratio=0.42,
            price=90000,
            avg_video_play_median=120000,
            expected_cpm=110,
            average_completion_rate=0.03,
            average_interaction_rate=0.012,
            monthly_growth_rate=0.003,
            monthly_connected_users=220000,
            monthly_deep_users=60000,
        )

        shortlist, filtered = rank_shortlist_candidates(requirement, [weak, strong], shortlist_limit=5)

        self.assertGreaterEqual(len(shortlist), 1)
        self.assertEqual(shortlist[0].creator.creator_name, "Demo Beauty Creator")
        self.assertGreaterEqual(sum(filtered.values()), 1)
        self.assertIsInstance(filtered, dict)

    def test_shortlist_runner_preview_plan_includes_reference_docs(self) -> None:
        runner = ShortlistRunner()
        response = runner.preview_plan(
            ShortlistPlanRequest(
                raw_text="Brand: Luminelle\nProduct: Velvet Lip Glaze\nBudget: 80000 RMB\nbeauty seeding brief",
                collection_limit=5,
                shortlist_limit=3,
            )
        )

        self.assertEqual(response.search_plan.collection_limit, 5)
        self.assertGreaterEqual(len(response.reference_docs), 1)


if __name__ == "__main__":
    unittest.main()
