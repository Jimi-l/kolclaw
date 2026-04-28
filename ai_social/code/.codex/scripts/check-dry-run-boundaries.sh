#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

paths=(
  "$repo_root/AGENTS.md"
  "$repo_root/.codex/README.md"
  "$repo_root/.codex/CONVENTIONS.md"
  "$repo_root/.codex/skills/README.md"
  "$repo_root/.codex/agents/README.md"
  "$repo_root/.codex/skills/brief-parse/SKILL.md"
  "$repo_root/.codex/skills/douyin-scout/SKILL.md"
  "$repo_root/.codex/skills/xingtu-enrich/SKILL.md"
  "$repo_root/.codex/skills/creator-tagging/SKILL.md"
  "$repo_root/.codex/skills/commercial-score/SKILL.md"
  "$repo_root/.codex/skills/outreach-draft/SKILL.md"
  "$repo_root/.codex/agents/brief_analyst.toml"
  "$repo_root/.codex/agents/brief-intake-agent.md"
  "$repo_root/.codex/agents/douyin-scout-agent.md"
  "$repo_root/.codex/agents/xingtu-enrichment-agent.md"
  "$repo_root/.codex/agents/tagging-agent.md"
  "$repo_root/.codex/agents/commercial-scoring-agent.md"
  "$repo_root/.codex/agents/outreach-drafting-agent.md"
  "$repo_root/.codex/agents/shortlist-orchestrator-agent.md"
  "$repo_root/packages/brief_parser/docs/contract.md"
  "$repo_root/apps/api/app/schemas/brief_parse.py"
)

for path in "${paths[@]}"; do
  if ! grep -qi 'dry_run' "$path"; then
    echo "Expected dry_run boundary in: $path" >&2
    exit 1
  fi
done

if grep -RniE '(send($| )|submit($| )|log in|login($| )|follow( creator| account| on )|like($| )|comment($| )|write to feishu|update feishu|update wecom|update crm)' \
  "$repo_root/.codex/skills" "$repo_root/.codex/agents" \
  | grep -viE 'do not|no |draft only|blocked|guardrails|placeholder' >/dev/null; then
  echo "Potential live side-effect wording found outside a guardrail context." >&2
  exit 1
fi

echo "Dry-run boundary checks passed."
