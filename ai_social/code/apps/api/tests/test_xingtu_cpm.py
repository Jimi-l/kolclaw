from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from app.api.routes_xingtu_cpm import sample_xingtu_cpm  # noqa: E402
from app.schemas.xingtu_cpm import ChartPoint, ScreenshotType, VlmExtractedPayload, VlmExtractionResult, XingtuCpmInput, XingtuCpmRuleConfig  # noqa: E402
from app.services.xingtu_cpm_extraction import parse_images, parse_vlm_extracted_payload  # noqa: E402
from app.services.xingtu_cpm_rules import bucketed_mode, evaluate_xingtu_cpm  # noqa: E402
from app.services.xingtu_cpm_vlm import parse_vlm_payload  # noqa: E402
from app.utils.xingtu_units import parse_int  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "xingtu_cpm"
REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_IMAGE_ROOT = REPO_ROOT / "data" / "xingtu_cpm" / "real_images"


def _vlm_payload(post_count_30d: int | None = 7) -> VlmExtractedPayload:
    natural = [19097000, 15970000, 5601000, 13507000, 18380000, 11547000, 25130000, 10585000, 8852000, 8670000, 16114000, 16677000, 12714000, 11457000, 6934000]
    sponsored = [16469000, 16510000, 15448000, 22821000, 23283000, 3147000, 10628000, 14824000, 32698000, 84248000, 24004000, 15930000, 5601000, 13507000, 8852000]
    personal_dates = ["26/02/11", "26/02/13", "26/02/17", "26/02/21", "26/02/27", "26/03/04", "26/03/08", "26/03/17", "26/03/21", "26/03/24", "26/03/27", "26/04/03", "26/04/06", "26/04/10", "26/04/13"]
    star_dates = ["25/10/25", "25/11/17", "25/12/05", "25/12/12", "25/12/17", "25/12/18", "25/12/26", "26/01/06", "26/01/17", "26/01/23", "26/01/30", "26/02/13", "26/02/17", "26/02/21", "26/03/21"]
    return VlmExtractedPayload(
        detected_screenshot_types=[
            ScreenshotType.OVERVIEW_PRICING,
            ScreenshotType.VALUE_PERSONAL_VIDEO,
            ScreenshotType.LATEST15_PERSONAL_CHART,
            ScreenshotType.LATEST15_STAR_CHART,
        ],
        creator_name="Example Creator A",
        price_20s=300000,
        price_20_60s=300000,
        price_60s_plus=320000,
        post_count_30d=post_count_30d,
        platform_expected_cpm=26.1,
        platform_expected_play=11513000,
        natural_plays=natural,
        sponsored_plays=sponsored,
        personal_chart_points=[ChartPoint(date=item[0], play=item[1], image_name="latest15_personal_chart.png") for item in zip(personal_dates, natural)],
        star_chart_points=[ChartPoint(date=item[0], play=item[1], image_name="latest15_star_chart.png") for item in zip(star_dates, sponsored)],
    )


class XingtuCpmTests(unittest.TestCase):
    def test_unit_parser_handles_cn_units(self) -> None:
        self.assertEqual(parse_int("80万"), 800000)
        self.assertEqual(parse_int("1.2亿"), 120000000)
        self.assertEqual(parse_int("4481.4w"), 44814000)

    def test_bucketed_mode_is_not_exact_mode(self) -> None:
        config = XingtuCpmRuleConfig.model_validate({"bucketed_mode": {"bucket_ratio": 0.25, "min_bucket_width": 10}})
        value = bucketed_mode([100, 105, 110, 300, 305], config)
        self.assertEqual(value, 102)

    def test_vlm_schema_parse_accepts_chart_points(self) -> None:
        payload, warning = parse_vlm_payload(
            '{"detected_screenshot_types":["latest15_personal_chart"],"personal_chart_points":[{"date":"26/03/06","play":5594000}]}'
        )

        self.assertIsNone(warning)
        self.assertEqual(payload.detected_screenshot_types, [ScreenshotType.LATEST15_PERSONAL_CHART])
        self.assertEqual(payload.personal_chart_points[0].play, 5594000)

    def test_vlm_schema_parse_invalid_json_returns_warning(self) -> None:
        payload, warning = parse_vlm_payload("not json")

        self.assertIsNotNone(warning)
        self.assertTrue(payload.warnings)

    def test_vlm_schema_parse_normalizes_string_units(self) -> None:
        payload, warning = parse_vlm_payload(
            """
            {
              "detected_screenshot_types":["overview_pricing","latest15_personal_chart","latest15_star_chart"],
              "price_20s":"￥168,000",
              "platform_expected_play":"1,151.3w",
              "platform_expected_cpm":"26.1",
              "natural_plays":["559.4w","729.9万"],
              "sponsored_plays":["840.4w","659.5w"],
              "personal_chart_points":[{"date":"26/03/06","play":"559.4w"}],
              "star_chart_points":[{"date":"26/03/10","play":"840.4万"}]
            }
            """
        )

        self.assertIsNone(warning)
        self.assertEqual(payload.price_20s, 168000)
        self.assertEqual(payload.platform_expected_play, 11513000)
        self.assertEqual(payload.platform_expected_cpm, 26.1)
        self.assertEqual(payload.natural_plays, [5594000, 7299000])
        self.assertEqual(payload.sponsored_plays, [8404000, 6595000])
        self.assertEqual(payload.personal_chart_points[0].play, 5594000)

    def test_vlm_schema_parse_unwraps_nested_data(self) -> None:
        payload, warning = parse_vlm_payload('{"data":{"detected_screenshot_types":["overview_pricing"],"price_20s":"￥168,000"}}')

        self.assertIsNone(warning)
        self.assertEqual(payload.detected_screenshot_types, [ScreenshotType.OVERVIEW_PRICING])
        self.assertEqual(payload.price_20s, 168000)

    def test_vlm_schema_parse_drops_bad_field_without_clearing_payload(self) -> None:
        payload, warning = parse_vlm_payload('{"price_20s":"bad","natural_plays":["559.4w","bad"]}')

        self.assertIsNone(warning)
        self.assertEqual(payload.price_20s, None)
        self.assertEqual(payload.natural_plays, [5594000])
        self.assertTrue(any("price_20s" in item for item in payload.warnings))
        self.assertTrue(any("natural_plays[1]" in item for item in payload.warnings))

    def test_parse_vlm_payload_derives_commercial_stats(self) -> None:
        result = parse_vlm_extracted_payload(_vlm_payload(), XingtuCpmRuleConfig(), vlm_model_used="fixture")

        self.assertEqual(result.extraction_engine_used, "vlm")
        self.assertEqual(result.parsed_input.ad_median_play, 15930000)
        self.assertEqual(result.parsed_input.ad_bucketed_mode_play, 14824000)
        self.assertEqual(result.field_sources["ad_median_play"], "derived")
        self.assertEqual(result.field_sources["ad_bucketed_mode_play"], "derived")

    def test_post_count_can_be_derived_from_chart_dates(self) -> None:
        result = parse_vlm_extracted_payload(_vlm_payload(post_count_30d=None), XingtuCpmRuleConfig(), vlm_model_used="fixture")

        self.assertEqual(result.parsed_input.post_count_30d_source, "chart_dates")
        self.assertEqual(result.parsed_input.chart_date_count_30d_personal, 8)
        self.assertEqual(result.parsed_input.chart_date_count_30d_star, 1)
        self.assertEqual(result.parsed_input.post_count_30d, 9)

    def test_post_count_prefers_chart_dates_over_value_page_field(self) -> None:
        result = parse_vlm_extracted_payload(_vlm_payload(post_count_30d=7), XingtuCpmRuleConfig(), vlm_model_used="fixture")

        self.assertEqual(result.parsed_input.post_count_30d_source, "chart_dates")
        self.assertEqual(result.parsed_input.post_count_30d, 9)
        self.assertTrue(any("post_count_30d=7" in warning for warning in result.warnings))

    def test_post_count_zero_is_overridden_when_chart_dates_show_activity(self) -> None:
        result = parse_vlm_extracted_payload(_vlm_payload(post_count_30d=0), XingtuCpmRuleConfig(), vlm_model_used="fixture")

        self.assertEqual(result.parsed_input.post_count_30d_source, "chart_dates")
        self.assertEqual(result.parsed_input.post_count_30d, 9)
        self.assertTrue(any("post_count_30d=0" in warning for warning in result.warnings))
        assessment = evaluate_xingtu_cpm(result.parsed_input, XingtuCpmRuleConfig())
        self.assertNotEqual(assessment.commercial_level, "NO_COMMERCIAL_VALUE")

    def test_assessment_uses_play_basis_names_and_star_basis(self) -> None:
        parse_result = parse_vlm_extracted_payload(_vlm_payload(), XingtuCpmRuleConfig(), vlm_model_used="fixture")
        assessment = evaluate_xingtu_cpm(parse_result.parsed_input, XingtuCpmRuleConfig())

        self.assertEqual(assessment.primary_pool.center, 5601000)
        self.assertEqual(assessment.primary_pool.source, "observed_cluster")
        self.assertTrue(assessment.primary_pool.age_weighted)
        self.assertEqual(assessment.secondary_pool.source if assessment.secondary_pool else None, "observed_cluster")
        self.assertEqual(assessment.commercial_primary_pool.center if assessment.commercial_primary_pool else None, 8852000)
        self.assertEqual(assessment.commercial_primary_pool.source if assessment.commercial_primary_pool else None, "observed_cluster")
        self.assertEqual(assessment.commercial_cpm_play_basis, 8852000)
        self.assertEqual(assessment.natural_cpm_play_basis, 5601000)
        self.assertEqual(assessment.predicted_ad_play, assessment.commercial_cpm_play_basis)
        self.assertEqual(assessment.base_predicted_play, assessment.commercial_cpm_play_basis)
        self.assertEqual(assessment.cpm_by_tier["20s"].predicted_cpm, 33.89)
        self.assertEqual(assessment.cpm_by_tier["20s"].natural_cpm, 53.56)
        self.assertEqual(assessment.cpm_by_tier["20s"].commercial_cpm_play_basis_source, "star_chart_primary_pool")
        self.assertEqual(assessment.cpm_by_tier["20s"].natural_cpm_play_basis_source, "natural_primary_pool")

    def test_low_post_count_does_not_discount_single_video_play_pools(self) -> None:
        natural = [7147000, 8267000, 11630000, 9660000, 16231000, 9803000, 28268000, 4467000, 4269000, 5064000, 8127000, 6226000, 6839000, 8037000, 1252000]
        sponsored = [8698000, 14719000, 21068000, 7778000, 16941000, 36782000, 17165000, 8092000, 3799000, 17172000, 8340000, 9528000, 3820000, 10177000, 9057000]
        payload = XingtuCpmInput(
            natural_plays=natural,
            sponsored_plays=sponsored,
            post_count_30d=4,
            price_20s=100000,
            price_20_60s=100000,
            price_60s_plus=100000,
        )

        assessment = evaluate_xingtu_cpm(payload, XingtuCpmRuleConfig())

        self.assertEqual(assessment.debug["activity_discount_factor"], 2.2)
        self.assertEqual(assessment.primary_pool.center, 4467000)
        self.assertEqual(assessment.commercial_primary_pool.center if assessment.commercial_primary_pool else None, 3799000)
        self.assertEqual(assessment.natural_cpm_play_basis, 4467000)
        self.assertEqual(assessment.commercial_cpm_play_basis, 3799000)
        self.assertIsNotNone(assessment.secondary_pool)
        self.assertIsNotNone(assessment.commercial_secondary_pool)
        self.assertEqual(assessment.commercial_secondary_pool.source if assessment.commercial_secondary_pool else None, "observed_cluster")
        self.assertIn("近30天发文数不足6条，已进行折损", assessment.review_reasons)

    def test_broad_single_layer_gets_estimated_secondary_pool(self) -> None:
        payload = XingtuCpmInput(
            natural_plays=[100, 105, 110, 115, 120, 125, 130, 135],
            sponsored_plays=[1000, 1080, 1160, 1240, 1320, 1400, 1480, 1560],
            post_count_30d=8,
            price_20s=10000,
            price_20_60s=10000,
            price_60s_plus=10000,
        )

        assessment = evaluate_xingtu_cpm(payload, XingtuCpmRuleConfig())

        self.assertEqual(assessment.secondary_pool.source if assessment.secondary_pool else None, "quantile_fallback")
        self.assertTrue(assessment.secondary_pool.is_estimated if assessment.secondary_pool else False)
        self.assertEqual(assessment.commercial_secondary_pool.source if assessment.commercial_secondary_pool else None, "quantile_fallback")
        self.assertTrue(assessment.commercial_secondary_pool.is_estimated if assessment.commercial_secondary_pool else False)
        self.assertIn("次级流量池为分位估算，建议复核", assessment.review_reasons)

    def test_trend_metrics_include_natural_commercial_and_overall(self) -> None:
        payload = XingtuCpmInput(
            natural_plays=[8000000, 8200000, 7900000, 8100000, 1000000, 1100000, 900000, 950000],
            sponsored_plays=[3000000, 3100000, 3200000, 3300000, 3400000, 3500000, 3600000, 3700000],
            personal_chart_points=[ChartPoint(date=f"26/03/{index + 1:02d}", play=value) for index, value in enumerate([8000000, 8200000, 7900000, 8100000, 1000000, 1100000, 900000, 950000])],
            star_chart_points=[ChartPoint(date=f"26/03/{index + 1:02d}", play=value) for index, value in enumerate([3000000, 3100000, 3200000, 3300000, 3400000, 3500000, 3600000, 3700000])],
            post_count_30d=8,
            price_20s=100000,
            price_20_60s=100000,
            price_60s_plus=120000,
        )
        assessment = evaluate_xingtu_cpm(payload, XingtuCpmRuleConfig())

        self.assertEqual(assessment.natural_trend_metrics.trend_direction, "falling")
        self.assertEqual(assessment.commercial_trend_metrics.trend_direction, "rising")
        self.assertIsNotNone(assessment.overall_trend_metrics)
        self.assertIn("overall_trend", assessment.final_prediction_factors)

    def test_parse_images_auto_requires_vlm(self) -> None:
        with patch.dict("os.environ", {"XINGTU_CPM_VLM_ENABLED": "false"}, clear=False):
            with self.assertRaises(Exception):
                parse_images([Path("dummy.png")], mode="auto", config=XingtuCpmRuleConfig())

    def test_legacy_extraction_mode_is_gone(self) -> None:
        with self.assertRaises(Exception):
            parse_images([Path("dummy.png")], mode="legacy_mode", config=XingtuCpmRuleConfig())

    def test_api_sample_is_fixture(self) -> None:
        response = sample_xingtu_cpm()
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["assessment"]["commercial_level"], "A")
        self.assertEqual(payload["parse_result"]["extraction_engine_used"], "fixture")
        self.assertEqual(payload["parse_result"]["missing_required_screenshot_types"], [])

    def test_vlm_only_without_config_returns_503(self) -> None:
        client = TestClient(app)
        with patch.dict("os.environ", {"XINGTU_CPM_VLM_ENABLED": "false"}, clear=False):
            response = client.post("/api/xingtu-cpm/analyze-vlm-only", files=[("files", ("x.png", b"not-an-image", "image/png"))])

        self.assertEqual(response.status_code, 503)

    def test_api_vlm_only_accepts_string_units_from_model(self) -> None:
        class FakeVlm:
            model = "fake-vlm"

            def extract_from_images(self, image_paths):
                payload, warning = parse_vlm_payload(
                    '{"detected_screenshot_types":["overview_pricing","latest15_personal_chart","latest15_star_chart"],'
                    '"price_20s":"￥168,000","natural_plays":["559.4w","729.9w","1080.3w","1930w","2331.1w","931.2w","537.3w","334.1w"],'
                    '"sponsored_plays":["840.4w","659.5w","1333w","319.8w","394.4w","1859w","1980.7w","981.4w"]}'
                )
                return VlmExtractionResult(payload=payload, model=self.model, warning=warning, raw_response='{"natural_plays":["559.4w"]}')

        client = TestClient(app)
        with patch("app.services.xingtu_cpm_extraction.get_vlm_extractor", return_value=FakeVlm()):
            response = client.post("/api/xingtu-cpm/analyze-vlm-only", files=[("files", ("x.png", b"not-an-image", "image/png"))])

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["parse_result"]["parsed_input"]["price_20s"], 168000)
        self.assertEqual(payload["parse_result"]["parsed_input"]["natural_plays"][0], 5594000)
        self.assertEqual(payload["parse_result"]["parsed_input"]["sponsored_plays"][0], 8404000)
        self.assertIn("vlm_raw_response_preview", payload["parse_result"])

    def test_api_analyze_writes_debug_run_log(self) -> None:
        class FakeVlm:
            model = "fake-vlm"

            def extract_from_images(self, image_paths):
                payload, warning = parse_vlm_payload(
                    '{"detected_screenshot_types":["overview_pricing","latest15_personal_chart","latest15_star_chart"],'
                    '"price_20s":"￥168,000","natural_plays":["559.4w","729.9w","1080.3w","1930w","2331.1w","931.2w","537.3w","334.1w"],'
                    '"sponsored_plays":["840.4w","659.5w","1333w","319.8w","394.4w","1859w","1980.7w","981.4w"]}'
                )
                return VlmExtractionResult(payload=payload, model=self.model, warning=warning, raw_response='{"natural_plays":["559.4w"]}')

        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmpdir, patch("app.services.xingtu_cpm_extraction.get_vlm_extractor", return_value=FakeVlm()), patch.dict(
            "os.environ",
            {"XINGTU_CPM_DEBUG_RUN_LOG_DIR": tmpdir, "XINGTU_CPM_DEBUG_RUN_LOG_ENABLED": "true"},
            clear=False,
        ):
            response = client.post("/api/xingtu-cpm/analyze-vlm-only", files=[("files", ("x.png", b"not-an-image", "image/png"))])
            logs = sorted(Path(tmpdir).glob("*.json"))
            log_payload = __import__("json").loads(logs[0].read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(logs), 1)
        self.assertEqual(log_payload["status"], "ok")
        self.assertEqual(log_payload["upload_filenames"], ["x.png"])
        self.assertIn("parse_result", log_payload["response"])
        self.assertIn("assessment", log_payload["response"])

    def test_real_image_fixture_sets_can_smoke_vlm_when_enabled(self) -> None:
        if os.getenv("XINGTU_CPM_RUN_REAL_IMAGE_SMOKE") != "1":
            self.skipTest("Set XINGTU_CPM_RUN_REAL_IMAGE_SMOKE=1 to run real image VLM smoke.")

        root = REAL_IMAGE_ROOT
        required = ["overview_pricing.png", "value_personal_video.png", "latest15_personal_chart.png", "latest15_star_chart.png"]
        sets = [path for path in sorted(root.glob("eg_*")) if all((path / name).exists() for name in required)]
        if not sets:
            self.skipTest(f"No complete real image fixture sets found under {root}")

        client = TestClient(app)
        for folder in sets:
            files = []
            handles = []
            try:
                for name in required:
                    handle = (folder / name).open("rb")
                    handles.append(handle)
                    files.append(("files", (name, handle, "image/png")))
                response = client.post("/api/xingtu-cpm/analyze-vlm-only", files=files, timeout=180)
            finally:
                for handle in handles:
                    handle.close()

            self.assertEqual(response.status_code, 200, folder.name)
            payload = response.json()
            self.assertIn("parse_result", payload)
            self.assertIn("assessment", payload)


if __name__ == "__main__":
    unittest.main()
