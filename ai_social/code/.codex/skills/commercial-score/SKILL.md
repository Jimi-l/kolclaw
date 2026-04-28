# commercial-score

Use this skill when the task is to score or rank creators with explainable commercial heuristics.

## Default Mode

- `dry_run: true`
- No external side effects

## Primary References

- `AGENTS.md`
- `apps/api/app/services/shortlist_scoring.py`
- `apps/api/app/schemas/shortlist.py`
- `external_docs/operational/选号prompt.txt`
- `docs/v1_shortlist_demo.md`

## Inputs

- Structured requirement
- Normalized creator detail
- Optional shortlist candidate list

## Workflow

1. Apply hard-fail reasoning before soft scoring.
2. Reuse the repo's explainable dimensions when possible:
   `brief_match`, `audience_match`, `content_fit`, `quality_activity`, `commercial_signal`, `risk_penalty`.
3. If using extra heuristics from `选号prompt.txt`, label them as business heuristics rather than observed platform truth.
4. Produce auditable rationales, not only totals.

## Output Contract

- `hard_fail_reasons`
- `score_breakdown`
- `recommendation_level`
- `recommendation_reason`
- `risk_flags`
- `evidence_notes`

## Guardrails

- Never hide assumptions inside a final score.
- Keep derived estimates separate from observed metrics.
- Avoid ranking candidates with missing core evidence without flagging the gap.
- Keep `dry_run: true`; this skill computes and explains only.
