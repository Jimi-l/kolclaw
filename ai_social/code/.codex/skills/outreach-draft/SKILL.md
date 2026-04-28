# outreach-draft

Use this skill when the task is to draft outreach copy for a creator that already passed shortlist review.

## Default Mode

- `dry_run: true`
- Draft only; do not send

## Primary References

- `AGENTS.md`
- `apps/api/app/schemas/shortlist.py`
- Shortlist output from `shortlist_runner.py`

## Inputs

- Approved creator profile
- Campaign brief summary
- Offer framing, product hooks, and contact context

## Workflow

1. Summarize the campaign ask in plain language.
2. Adapt tone to the candidate's content style and brand fit.
3. Produce message variants for review, not delivery.
4. Surface missing commercial details that should be confirmed before real outreach.

## Output Contract

- `channel`
- `subject_or_opening`
- `message_draft`
- `follow_up_draft`
- `personalization_notes`
- `missing_confirmation_items`

## Guardrails

- Do not imply the outreach was sent.
- Do not promise unavailable budgets, deliverables, or timelines.
- Draft only after shortlist review or explicit user instruction.
- Keep `dry_run: true`.
