# Codex Conventions / Codex 运行约定

This file defines the repo-local Codex contract for KOLClaw.

## 1. Layering

There is only one runtime Codex tree in this repo:

- [`.codex`](/home/tuo/project/ai_social/code/.codex)

There is only one human/business editing layer for operational methodology:

- [`external_docs/operational`](/home/tuo/project/ai_social/external_docs/operational)

Do not create parallel Chinese and English runtime trees.

## 2. File Roles

### Runtime-facing for Codex

- [AGENTS.md](/home/tuo/project/ai_social/code/AGENTS.md)
- [`.codex/skills/*/SKILL.md`](/home/tuo/project/ai_social/code/.codex/skills)
- [`.codex/agents/*.toml`](/home/tuo/project/ai_social/code/.codex/agents)
- [`.codex/hooks.json`](/home/tuo/project/ai_social/code/.codex/hooks.json)
- [`.codex/scripts/*`](/home/tuo/project/ai_social/code/.codex/scripts)
- [`.codex/README.md`](/home/tuo/project/ai_social/code/.codex/README.md)

These files should stay concise, stable, and execution-bounded.

### Business-facing for humans

- [`external_docs/operational/KOLclaw_媒介执行workflow_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KOLclaw_媒介执行workflow_codex.md)
- [`external_docs/operational/KolClaw_达人标签_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KolClaw_达人标签_codex.md)
- Other operational reference docs in [`external_docs/operational`](/home/tuo/project/ai_social/external_docs/operational)

These files are the editable business methodology source of truth. They may be Chinese-first or bilingual.

### Examples or design notes only

- [`.codex/agents/*.md`](/home/tuo/project/ai_social/code/.codex/agents)

These markdown files are placeholder design notes and ownership sketches. They are not live automation configs.

## 3. Directory Convention

### [`.codex/skills/`](/home/tuo/project/ai_social/code/.codex/skills)

- One folder per stable skill identifier.
- Folder names should stay English/ASCII and match pipeline stage names.
- Each skill folder should contain one `SKILL.md`.
- `SKILL.md` should define triggers, inputs, outputs, constraints, non-goals, and safety posture.
- If business logic is detailed or frequently changing, the skill should point to business-source markdown instead of copying it inline.

### [`.codex/agents/`](/home/tuo/project/ai_social/code/.codex/agents)

- `*.toml` is the intended runtime-facing agent config format.
- `*.md` may exist as design notes or migration placeholders.
- Agents should own read, analyze, normalize, rank, or plan work before they own any side effects.
- Live autonomous execution is intentionally not enabled in this repo yet.

### [`.codex/hooks.json`](/home/tuo/project/ai_social/code/.codex/hooks.json)

- Hooks must stay validation-only.
- Hooks may check structure, parseability, or dry-run boundaries.
- Hooks must not trigger platform actions, writes to external systems, or outbound communication.

### [`.codex/scripts/`](/home/tuo/project/ai_social/code/.codex/scripts)

- Scripts should support local validation only.
- Scripts should fail loudly on safety boundary violations.
- Avoid brittle checks that pretend to validate production behavior.

## 4. Chinese / English Agreement

Use this exact rule set:

- Runtime identifiers such as skill names, folder names, script names, and agent IDs stay stable and preferably English/ASCII.
- Business methodology content may be Chinese or bilingual.
- Chinese-facing operational markdown under [`external_docs/operational`](/home/tuo/project/ai_social/external_docs/operational) is the editable business source of truth.
- Codex runtime docs stay concise and point back to those business docs.
- Future updates must keep runtime docs and business-source docs synchronized.

## 5. Canonical Business Sources

Primary operational sources for the current scaffold:

- [`external_docs/operational/KOLclaw_媒介执行workflow_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KOLclaw_媒介执行workflow_codex.md)
- [`external_docs/operational/KolClaw_达人标签_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KolClaw_达人标签_codex.md)
- [`external_docs/operational/AI智能巡号_抖音版_执行提示词_V3.md`](/home/tuo/project/ai_social/external_docs/operational/AI智能巡号_抖音版_执行提示词_V3.md)
- [`external_docs/operational/AI智能巡号_星图数据补充_执行提示词.md`](/home/tuo/project/ai_social/external_docs/operational/AI智能巡号_星图数据补充_执行提示词.md)
- [`external_docs/operational/选号prompt.txt`](/home/tuo/project/ai_social/external_docs/operational/选号prompt.txt)

## 6. Safety Contract

- Default `dry_run: true`
- No external side effects
- No fake production claims
- No duplicate runtime trees
- No speculative integrations added just to make the scaffold look complete
