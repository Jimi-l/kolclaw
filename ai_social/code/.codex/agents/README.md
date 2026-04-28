# Project Agents

This directory supports two file roles.

## Runtime-facing agent configs

- `*.toml`

These are the intended project-scoped custom agent config files.
They should stay conservative and should not claim live automation that the repo does not have.
All runtime-facing agent configs in this repo should keep `dry_run: true`.

Current example:

- [`brief_analyst.toml`](/home/tuo/project/ai_social/code/.codex/agents/brief_analyst.toml)

## Placeholder design docs

- `*.md`

These markdown files describe ownership, handoff intent, and future decomposition ideas.
They are not active runtime configs.

## How To Add Future Agents

1. Start with a focused ownership boundary.
2. Prefer read, analyze, normalize, review, or plan responsibilities first.
3. Add a `*.toml` config only when the role is stable enough to deserve a runtime identity.
4. Keep `dry_run: true` and no-external-side-effects language explicit.
5. If useful, pair the TOML with a short markdown note explaining handoffs.

## Why Live Execution Is Not Enabled

- The current repo is a V1 shortlist assistant, not a production media automation platform.
- Business docs describe a broader workflow than the checked-in code currently implements.
- Safety posture for this repo is still validation-first and dry-run-first.

Until that changes, agent configs should stay within read, analyze, and planning boundaries.
