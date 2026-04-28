# douyin-scout

Use this skill when the task is to plan or summarize Douyin scouting work for potential creators before Xingtu enrichment.

## Default Mode

- `dry_run: true`
- No login, browsing, likes, follows, comments, or spreadsheet writes

## Primary References

- `AGENTS.md`
- `external_docs/operational/AI智能巡号_抖音版_执行提示词_V3.md`
- `external_docs/operational/选号prompt.txt`
- `docs/v1_shortlist_demo.md`

## Inputs

- Campaign requirement or category focus
- Candidate seed list, creator names, or observation notes
- Optional viral-threshold rules from the business docs

## Workflow

1. Translate the brief into a scouting checklist.
2. Define what counts as a promising observation:
   viral threshold, recent content consistency, account quality, and obvious exclusions.
3. Produce a dry-run scouting plan or summarize provided observations.
4. Keep scouting evidence separate from commercial conclusions.

## Output Contract

- `scouting_objective`
- `observation_checklist`
- `candidate_observations`
- `reasons_to_escalate_to_xingtu`
- `blocked_actions`

## Guardrails

- Do not simulate real account training behavior.
- Do not execute autonomous browsing or interaction loops from the prompt doc.
- Do not claim Xingtu-quality conclusions from Douyin-only evidence.
- Keep `dry_run: true` until an explicit browser automation layer is implemented and reviewed.
