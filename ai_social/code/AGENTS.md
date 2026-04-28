# KOLClaw Codex Guide

This repository uses one runtime Codex layer and one business-editing layer.

## Current Boundary

Current V1 product scope:

`brief -> structured requirement -> Xingtu search plan -> live Xingtu collection -> heuristic scoring -> shortlist`

Longer-term business pipeline:

`brief intake -> Douyin scouting -> creator tagging -> Xingtu enrichment -> commercial scoring -> shortlist review -> outreach drafting -> human approval -> external execution`

The checked-in code only supports the V1 shortlist layer today. Do not describe future workflow stages as production automation.

## Canonical Stages

- `brief-parse`
- `douyin-scout`
- `creator-tagging`
- `xingtu-enrich`
- `commercial-score`
- `outreach-draft`

These stage identifiers are the stable runtime names for `.codex/skills/`, agent ownership, and future workflow handoffs.

## Safety Boundary

- Default mode is always `dry_run: true`.
- Hooks must stay validation-only.
- No real external side effects from the scaffold:
  no browser logins, no likes/follows/comments, no Feishu writes, no WeCom sends, no CRM updates, no outbound messaging, no spreadsheet mutation.
- Future side-effecting behavior must be added behind explicit `dry_run` gates and separately reviewed implementation.

## Source Of Truth

Runtime-facing Codex assets live under:

- `.codex/skills/`
- `.codex/agents/`
- `.codex/hooks.json`
- `.codex/scripts/`
- `.codex/README.md`
- `.codex/CONVENTIONS.md`

Primary business-source markdown lives under:

- `external_docs/operational/KOLclaw_媒介执行workflow_codex.md`
- `external_docs/operational/KolClaw_达人标签_codex.md`

Repo contracts remain authoritative for current executable structure:

- `apps/api/app/schemas/shortlist.py`
- `apps/api/app/schemas/xingtu.py`
- `apps/api/app/services/shortlist_runner.py`

## Bilingual Layering Rule

- Runtime identifiers stay stable, English, and ASCII where possible.
- Chinese or bilingual methodology belongs in business-source docs.
- Runtime docs stay concise and point back to business-source docs instead of duplicating them.
- When business methodology changes, update both the relevant business-source markdown and the linked runtime guidance so they remain synchronized.

See [`.codex/CONVENTIONS.md`](/home/tuo/project/ai_social/code/.codex/CONVENTIONS.md) for the full repo-local convention.
