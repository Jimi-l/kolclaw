# xingtu-enrich

Use this skill when the task is to map a creator or shortlist candidate into the normalized Xingtu detail model used by the repo.

## Default Mode

- `dry_run: true`
- No real browser login, no platform queries, no external writes

## Primary References

- `AGENTS.md`
- `apps/api/app/schemas/xingtu.py`
- `apps/api/app/services/xingtu_workflow.py`
- `packages/xingtu_enrichment/docs/workflow_notes.md`
- `external_docs/operational/AI智能巡号_星图数据补充_执行提示词.md`

## Inputs

- Creator names or candidate rows
- Existing Xingtu row/detail data
- A search plan or filter intent

## Workflow

1. Map requested fields onto `XingtuFilterConfig`, `XingtuCreatorRow`, or `XingtuCreatorDetail`.
2. Call out which values are observed, missing, derived, or still unresolved.
3. Preserve raw evidence alongside normalized fields.
4. Prepare dry-run enrichment payloads or field-mapping templates only.

## Output Contract

- `filter_intent`
- `field_mapping`
- `normalized_creator_detail`
- `missing_fields`
- `evidence_notes`

## Guardrails

- Never fabricate Xingtu metrics.
- Keep raw text sections separate from normalized numeric fields.
- Do not submit searches, click pages, or save screenshots in this scaffold.
- Keep `dry_run: true` until the enrichment path is explicitly activated.
