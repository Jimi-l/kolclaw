#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

required_files=(
  "$repo_root/AGENTS.md"
  "$repo_root/.codex/hooks.json"
  "$repo_root/.codex/README.md"
  "$repo_root/.codex/CONVENTIONS.md"
  "$repo_root/.codex/skills/README.md"
  "$repo_root/.codex/skills/brief-parse/SKILL.md"
  "$repo_root/.codex/skills/douyin-scout/SKILL.md"
  "$repo_root/.codex/skills/xingtu-enrich/SKILL.md"
  "$repo_root/.codex/skills/creator-tagging/SKILL.md"
  "$repo_root/.codex/skills/commercial-score/SKILL.md"
  "$repo_root/.codex/skills/outreach-draft/SKILL.md"
  "$repo_root/.codex/agents/README.md"
  "$repo_root/.codex/agents/brief_analyst.toml"
  "$repo_root/.codex/agents/brief-intake-agent.md"
  "$repo_root/.codex/agents/douyin-scout-agent.md"
  "$repo_root/.codex/agents/xingtu-enrichment-agent.md"
  "$repo_root/.codex/agents/tagging-agent.md"
  "$repo_root/.codex/agents/commercial-scoring-agent.md"
  "$repo_root/.codex/agents/outreach-drafting-agent.md"
  "$repo_root/.codex/agents/shortlist-orchestrator-agent.md"
  "$repo_root/.codex/scripts/check-dry-run-boundaries.sh"
  "$repo_root/.codex/scripts/validate-brief-parse-contract.sh"
  "$repo_root/packages/brief_parser/docs/contract.md"
  "$repo_root/packages/common/schemas/brief_parse_input.schema.json"
  "$repo_root/packages/common/schemas/brief_parse_output.schema.json"
  "$repo_root/apps/api/app/schemas/brief_parse.py"
  "$repo_root/apps/api/app/services/brief_parse_interface.py"
  "$repo_root/apps/api/tests/test_brief_parse_contract.py"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing required scaffold file: $path" >&2
    exit 1
  fi
done

python3 - <<'PY' "$repo_root/.codex/hooks.json"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
with path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

hooks = data.get("hooks", {})
if set(hooks) != {"PostToolUse"}:
    raise SystemExit(f"hooks.json must only define PostToolUse, found: {sorted(hooks)}")

post_tool_use = hooks.get("PostToolUse", [])
if not post_tool_use:
    raise SystemExit("hooks.json must define hooks.PostToolUse")

commands = []
for item in post_tool_use:
    for hook in item.get("hooks", []):
        commands.append(hook.get("command", ""))

required = {
    "./.codex/scripts/validate-codex-scaffold.sh",
    "./.codex/scripts/validate-brief-parse-contract.sh",
    "./.codex/scripts/check-dry-run-boundaries.sh",
}
missing = required.difference(commands)
if missing:
    raise SystemExit(f"hooks.json is missing required commands: {sorted(missing)}")

for command in commands:
    if not command.startswith("./.codex/scripts/"):
        raise SystemExit(f"hooks.json command must stay inside .codex/scripts: {command}")
PY

python3 - <<'PY' "$repo_root/.codex/agents/brief_analyst.toml"
import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise SystemExit(f"tomllib unavailable: {exc}")

path = pathlib.Path(sys.argv[1])
with path.open("rb") as handle:
    data = tomllib.load(handle)

required_keys = {"name", "description", "model", "reasoning_effort", "dry_run", "instructions"}
missing = required_keys.difference(data)
if missing:
    raise SystemExit(f"Agent TOML missing required keys: {sorted(missing)}")

if data.get("dry_run") is not True:
    raise SystemExit("Agent TOML must keep dry_run = true")
PY

echo "Codex scaffold validation passed."
