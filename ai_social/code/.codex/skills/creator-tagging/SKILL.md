# creator-tagging

Use this skill when the task is to turn a structured brief into shortlist-ready creator tagging conditions.

## Business Contract

- Main spec: [business_contract.md](/home/tuo/project/ai_social/code/packages/creator_tagging/docs/business_contract.md)
- Field vocabulary: [field_dictionary.md](/home/tuo/project/ai_social/code/packages/creator_tagging/docs/field_dictionary.md)
- Business rules: [rules.md](/home/tuo/project/ai_social/code/packages/creator_tagging/docs/rules.md)
- Business examples: [examples.md](/home/tuo/project/ai_social/code/packages/creator_tagging/docs/examples.md)

## Inputs

- structured brief from `brief-parse`
- category / product direction
- audience direction
- style / tone direction
- exclusions and compliance notes
- geography and platform limits

## Conceptual Outputs

- required tags
- preferred tags
- exclusion tags
- review-only tags
- search-direction tags
- unresolved tagging gaps
- human review flags

## Guardrails

- Do not score creators inside this skill.
- Do not turn the full giant taxonomy into immediate V1 structured output.
- Mark unresolved mappings clearly.
- Keep `dry_run: true`.
