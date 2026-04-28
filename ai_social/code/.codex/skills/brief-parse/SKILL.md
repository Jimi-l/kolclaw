# brief-parse

Parse raw campaign briefs into the `brief-parse` business contract used by the V1 shortlist pipeline.

## Use This Skill When

- the task is to normalize raw brief text into a structured requirement
- the task is to validate brief completeness before search planning or shortlist work
- the task is to map red / green / yellow business priorities into repo buckets

## Do Not Use This Skill When

- the main task is scouting, tagging, Xingtu enrichment, scoring, or outreach
- the request is to execute any external workflow

## Runtime Contract

- Main spec: [business_contract.md](/home/tuo/project/ai_social/code/packages/brief_parser/docs/business_contract.md)
- Field vocabulary: [field_dictionary.md](/home/tuo/project/ai_social/code/packages/brief_parser/docs/field_dictionary.md)
- Business rules: [rules.md](/home/tuo/project/ai_social/code/packages/brief_parser/docs/rules.md)
- Business examples: [examples.md](/home/tuo/project/ai_social/code/packages/brief_parser/docs/examples.md)

Current Python / schema / fixture artifacts elsewhere in the repo should be treated as draft implementation artifacts, not the canonical source for this phase.

## Implementation Artifacts

- `packages/brief_parser/docs/contract.md`
- `packages/common/schemas/brief_parse_input.schema.json`
- `packages/common/schemas/brief_parse_output.schema.json`
- `apps/api/tests/fixtures/brief_parse`
- `apps/api/app/services/brief_parse_interface.py`

## Business Sources

- [`KOLclaw_媒介执行workflow_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KOLclaw_媒介执行workflow_codex.md)
- [`KolClaw_达人标签_codex.md`](/home/tuo/project/ai_social/external_docs/operational/KolClaw_达人标签_codex.md)

运行时只保留稳定字段与规则入口；详细业务方法论以业务源 markdown 为准。

## Execution Boundary

- `dry_run: true`
- no external side effects
- parse, normalize, and surface business issues only
