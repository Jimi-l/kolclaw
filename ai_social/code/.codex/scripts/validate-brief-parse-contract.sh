#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
api_root="$repo_root/apps/api"
venv_python="$repo_root/.venv/bin/python"

required_files=(
  "$repo_root/packages/brief_parser/docs/contract.md"
  "$repo_root/packages/common/schemas/brief_parse_input.schema.json"
  "$repo_root/packages/common/schemas/brief_parse_output.schema.json"
  "$repo_root/apps/api/app/schemas/brief_parse.py"
  "$repo_root/apps/api/app/services/brief_parse_interface.py"
  "$repo_root/apps/api/tests/test_brief_parse_contract.py"
  "$repo_root/apps/api/tests/fixtures/brief_parse/complete_brief_input.json"
  "$repo_root/apps/api/tests/fixtures/brief_parse/complete_brief_output.json"
  "$repo_root/apps/api/tests/fixtures/brief_parse/partial_brief_input.json"
  "$repo_root/apps/api/tests/fixtures/brief_parse/partial_brief_output.json"
  "$repo_root/apps/api/tests/fixtures/brief_parse/ambiguous_brief_input.json"
  "$repo_root/apps/api/tests/fixtures/brief_parse/ambiguous_brief_output.json"
  "$repo_root/.codex/skills/brief-parse/SKILL.md"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing brief-parse contract file: $path" >&2
    exit 1
  fi
done

PYTHONPATH="$api_root" "$venv_python" - <<'PY' "$repo_root"
import json
import sys
from pathlib import Path

from app.schemas.brief_parse import BriefParseInput, BriefParseOutput
from app.services.brief_parse_interface import parse_brief_with_contract

repo_root = Path(sys.argv[1])

schema_expectations = {
    repo_root / "packages/common/schemas/brief_parse_input.schema.json": BriefParseInput.model_json_schema(),
    repo_root / "packages/common/schemas/brief_parse_output.schema.json": BriefParseOutput.model_json_schema(),
}

for path, expected in schema_expectations.items():
    actual = json.loads(path.read_text(encoding="utf-8"))
    if actual != expected:
        raise SystemExit(f"Schema drift detected: {path}")

fixture_root = repo_root / "apps/api/tests/fixtures/brief_parse"
cases = (
    ("complete_brief_input.json", "complete_brief_output.json"),
    ("partial_brief_input.json", "partial_brief_output.json"),
    ("ambiguous_brief_input.json", "ambiguous_brief_output.json"),
)

for input_name, output_name in cases:
    input_payload = json.loads((fixture_root / input_name).read_text(encoding="utf-8"))
    output_payload = json.loads((fixture_root / output_name).read_text(encoding="utf-8"))

    validated_input = BriefParseInput.model_validate(input_payload)
    validated_output = BriefParseOutput.model_validate(output_payload)
    actual_output = parse_brief_with_contract(validated_input)

    if actual_output.model_dump(mode="json") != validated_output.model_dump(mode="json"):
        raise SystemExit(f"Fixture output mismatch for {input_name}")

skill_text = (repo_root / ".codex/skills/brief-parse/SKILL.md").read_text(encoding="utf-8")
required_mentions = [
    "packages/brief_parser/docs/contract.md",
    "packages/common/schemas/brief_parse_input.schema.json",
    "packages/common/schemas/brief_parse_output.schema.json",
    "apps/api/tests/fixtures/brief_parse",
    "apps/api/app/services/brief_parse_interface.py",
]
for mention in required_mentions:
    if mention not in skill_text:
        raise SystemExit(f"brief-parse skill is missing required reference: {mention}")

contract_text = (repo_root / "packages/brief_parser/docs/contract.md").read_text(encoding="utf-8")
for phrase in ("Input Contract", "Output Contract", "Business Rules", "Edge Cases", "Downstream Handoff"):
    if phrase not in contract_text:
        raise SystemExit(f"brief_parse_contract.md is missing section: {phrase}")
PY

PYTHONPATH="$api_root" "$venv_python" -m unittest "$repo_root/apps/api/tests/test_brief_parse_contract.py" >/dev/null

echo "Brief-parse contract validation passed."
