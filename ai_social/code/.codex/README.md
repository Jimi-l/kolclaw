# Codex Runtime Layer

This directory is the single runtime-facing Codex layer for KOLClaw.

## What Lives Here

- [`.codex/skills/`](/home/tuo/project/ai_social/code/.codex/skills): task-scoped runtime instructions
- [`.codex/agents/`](/home/tuo/project/ai_social/code/.codex/agents): project-scoped agent configs and agent design notes
- [`.codex/hooks.json`](/home/tuo/project/ai_social/code/.codex/hooks.json): validation-only hooks
- [`.codex/scripts/`](/home/tuo/project/ai_social/code/.codex/scripts): local validators used by hooks
- [`.codex/CONVENTIONS.md`](/home/tuo/project/ai_social/code/.codex/CONVENTIONS.md): repo-local Codex contract

## What Does Not Live Here

- Detailed business methodology
- Editable Chinese operational process docs
- Real outbound integrations

Those belong under [`external_docs/operational`](/home/tuo/project/ai_social/external_docs/operational).

Default posture for everything here is `dry_run: true`.
