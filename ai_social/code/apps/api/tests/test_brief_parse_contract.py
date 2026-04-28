from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.brief_parse import BriefParseInput, BriefParseOutput  # noqa: E402
from app.services.brief_parse_interface import parse_brief_with_contract  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "brief_parse"


class BriefParseContractTests(unittest.TestCase):
    def test_contract_fixtures_match_runtime_output(self) -> None:
        cases = (
            ("complete_brief_input.json", "complete_brief_output.json"),
            ("partial_brief_input.json", "partial_brief_output.json"),
            ("ambiguous_brief_input.json", "ambiguous_brief_output.json"),
        )

        for input_name, output_name in cases:
            with self.subTest(case=input_name):
                input_payload = json.loads((FIXTURE_ROOT / input_name).read_text(encoding="utf-8"))
                expected_output = json.loads((FIXTURE_ROOT / output_name).read_text(encoding="utf-8"))

                validated_input = BriefParseInput.model_validate(input_payload)
                actual_output = parse_brief_with_contract(validated_input)
                validated_output = BriefParseOutput.model_validate(expected_output)

                self.assertEqual(actual_output.model_dump(mode="json"), validated_output.model_dump(mode="json"))


if __name__ == "__main__":
    unittest.main()
