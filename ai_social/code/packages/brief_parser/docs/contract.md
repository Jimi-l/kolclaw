# Brief Parse Contract

## A. Purpose

`brief-parse` is the first backend-facing business contract in the KOLClaw pipeline.

It sits at:

`raw brief -> brief-parse -> structured requirement -> search planning / scouting / tagging / shortlist review`

Its job is to convert noisy brand-facing input into a normalized requirement bundle that the current repo can execute against.

Downstream dependencies:

- scouting uses category, audience, city, and keyword signals
- creator-tagging uses normalized category and audience vocabulary
- shortlist planning uses hard/preferred/negotiable buckets
- later scoring consumes the same `ShortlistRequirement` fields and parser diagnostics

This module does not perform creator discovery, ranking, or outreach.

### Execution Flow

Backend call boundary:

1. Accept `BriefParseInput`
2. Produce or validate a `ShortlistRequirement`
3. Run deterministic contract validation and diagnostics
4. Return `BriefParseOutput`

Current repo behavior:

- `apps/api/app/services/shortlist_brief_parser.py` produces the normalized requirement
- `apps/api/app/services/brief_parse_interface.py` adds deterministic diagnostics, priority mapping, and failure semantics

Future model-assisted behavior is allowed only at step 2.
Steps 3 and 4 should remain deterministic so backend validation behavior stays stable.

Primary business sources:

- `external_docs/operational/KOLclaw_媒介执行workflow_codex.md`
- `external_docs/operational/KolClaw_达人标签_codex.md`

Primary repo contracts:

- `apps/api/app/schemas/shortlist.py`
- `apps/api/app/services/shortlist_brief_parser.py`
- `apps/api/app/services/brief_parse_interface.py`

## B. Input Contract

Canonical runtime model:

- `apps/api/app/schemas/brief_parse.py` -> `BriefParseInput`

Machine-readable schema:

- `packages/common/schemas/brief_parse_input.schema.json`

### Input Shape

```json
{
  "raw_text": "string | null",
  "structured_requirement": "ShortlistRequirement | null",
  "metadata": {
    "brief_id": "string | null",
    "source_type": "manual_text | meeting_notes | chat_transcript | form_input | unknown",
    "source_language": "zh | en | mixed | unknown",
    "dry_run": true
  }
}
```

### Required Rules

- Exactly one of `raw_text` or `structured_requirement` must be provided.
- `metadata` is optional.
- `metadata.dry_run` defaults to `true` and is the only accepted value in the current repo.

### Missing Data Representation

- Missing scalar input values are `null`.
- Missing metadata may be omitted entirely.
- Missing optional metadata fields are `null` or default enum values.

### Invalid Input

The request is invalid if:

- both `raw_text` and `structured_requirement` are missing
- both are provided at the same time
- `raw_text` is empty or whitespace only
- `metadata.dry_run` is `false`
- extra undeclared top-level fields are provided

## C. Output Contract

Canonical runtime model:

- `apps/api/app/schemas/brief_parse.py` -> `BriefParseOutput`

Machine-readable schema:

- `packages/common/schemas/brief_parse_output.schema.json`

### Output Shape

```json
{
  "structured_requirement": "ShortlistRequirement",
  "parse_status": "complete | partial | needs_review",
  "parser_notes": ["string"],
  "priority_signals": [
    {
      "field": "string",
      "value": "string",
      "priority_color": "red | green | yellow",
      "mapped_bucket": "hard_constraints | preferred_constraints | negotiable_constraints",
      "rationale": "string",
      "source_text": "string | null"
    }
  ],
  "missing_information": ["BriefParseIssue"],
  "ambiguities": ["BriefParseIssue"],
  "contradictions": ["BriefParseIssue"],
  "unsupported_requirements": ["BriefParseIssue"],
  "defaults_applied": ["string"]
}
```

`BriefParseIssue` shape:

```json
{
  "code": "missing_field | ambiguous_field | contradictory_field | unsupported_requirement",
  "severity": "warning | error",
  "field": "string",
  "message": "string",
  "source_text": "string | null"
}
```

### Field Semantics

- `structured_requirement`
  wraps the current repo-side `ShortlistRequirement` and remains the main downstream payload.
- `parse_status`
  tells callers whether the requirement is search-ready, partial, or needs human review before use.
- `priority_signals`
  preserves the business priority interpretation in a backend-consumable form.
- `missing_information`
  lists required or recommended business fields that were absent after parsing.
- `ambiguities`
  lists vague or underspecified wording that needs confirmation.
- `contradictions`
  lists self-conflicting instructions detected deterministically.
- `unsupported_requirements`
  lists requests that the current V1 shortlist flow does not support.
- `defaults_applied`
  records parser-side defaults and derived heuristics.

### Nullability Rules

- Scalar fields inside `structured_requirement` may be `null` if not recoverable from the brief.
- Lists default to empty arrays, never `null`.
- `source_text` inside diagnostics may be `null`.

### Example Output

See:

- `apps/api/tests/fixtures/brief_parse/complete_brief_output.json`
- `apps/api/tests/fixtures/brief_parse/partial_brief_output.json`
- `apps/api/tests/fixtures/brief_parse/ambiguous_brief_output.json`

## D. Business Rules

### 1. Brief Decomposition

Business-source workflow fields are normalized into repo fields:

- brand & product info -> `brand`, `product_name`, `product_sku`, `product_category`
- target audience -> `target_audience`, `hard_constraints.audience_traits`, `preferred_constraints.audience_traits`
- KPI / objective -> `kpi_goals`
- budget -> `budget_total`, `hard_constraints.budget_cap_per_creator`
- content tone & style -> `content_style_tags`, `tone_tags`, `hard_constraints.content_themes`
- city / geography -> `city`, `hard_constraints.cities`
- compliance & avoid lists -> `compliance_notes`, `exclusions`, `hard_constraints.notes`
- optional or negotiable asks -> `optional_notes`, `negotiable_constraints.notes`

### 2. Red / Green / Yellow Mapping

Business-source priority model:

- red = hard bottom line
- green = preferred / scoring advantage
- yellow = negotiable / later review

Backend mapping rule in this repo:

- `red` -> `hard_constraints`
- `green` -> `preferred_constraints`
- `yellow` -> `negotiable_constraints`

Deterministic mapping behavior:

- explicit `Must`, `Required`, `硬性`, `必须`, `红色` lines map to `red`
- explicit `Prefer`, `优先`, `加分`, `绿色` lines map to `green`
- explicit `Optional`, `可选`, `可协商`, `黄色`, `可谈` lines map to `yellow`
- compliance notes and exclusions are always treated as `red`
- optional notes are treated as `yellow`
- unmarked core search-driving facts may still be placed in `hard_constraints` for V1 execution compatibility

Important implementation note:

The current repo-side `ShortlistRequirement` does not separately store “explicit business color” versus “default operational bucket”.
That gap is why `priority_signals` exists in the new contract wrapper.

### 3. Keyword Derivation

The parser derives `keywords` from the normalized requirement using:

- brand
- product name
- SKU
- primary category
- city
- creator categories
- target audience
- KPI goals
- content style tags
- tone tags

These keywords are downstream seeds, not direct search commands.

### 4. Unknown / Unsupported Requirements

The parser must surface, not hide:

- unsupported platforms outside current Douyin/Xingtu V1
- live-stream requirements in a short-video-first V1 flow
- vague budget or KPI wording that cannot be normalized
- category requests that directly conflict with exclusions

## E. Edge Cases / Failure Cases

### Incomplete Brief

Example:

- no budget
- no KPI
- no target audience

Behavior:

- `structured_requirement` still returns the best parsed partial structure
- missing required clusters appear in `missing_information`
- `parse_status = partial`

### Contradictory Brief

Example:

- `Must: pet creators`
- `Avoid: pets`

Behavior:

- both sides remain visible in `structured_requirement`
- contradiction is added to `contradictions`
- `parse_status = needs_review`

### Missing KPI

Behavior:

- `kpi_goals` stays empty
- error-level missing issue is emitted for `kpi_goals`
- search may continue only after human confirmation

### Missing Budget

Behavior:

- `budget_total = null`
- `budget_cap_per_creator = null`
- `min_fans_count` may fall back to the parser heuristic baseline if structurally possible
- error-level missing issue is emitted

### Vague Target Audience

Behavior:

- parser keeps any recoverable audience tags
- broad / vague language is added to `ambiguities`
- downstream audience fit should treat the result as partial

### Unclear Platform

Behavior:

- current V1 defaults platform to `douyin`
- default is recorded in `defaults_applied`
- if unsupported platforms are explicitly mentioned, emit `unsupported_requirements`

### Missing Compliance Constraints

Behavior:

- `compliance_notes` remains empty
- warning-level missing issue is emitted
- downstream shortlist review should require human confirmation before outreach or execution

## F. Downstream Handoff

### Scouting

Consume:

- `structured_requirement.keywords`
- `structured_requirement.product_category`
- `structured_requirement.hard_constraints`
- `structured_requirement.preferred_constraints`
- `priority_signals`

### Creator Tagging

Consume:

- `structured_requirement.product_category`
- `structured_requirement.target_audience`
- `structured_requirement.content_style_tags`
- `structured_requirement.tone_tags`
- business taxonomy from `KolClaw_达人标签_codex.md`

### Shortlist Review

Consume:

- full `structured_requirement`
- `missing_information`
- `ambiguities`
- `contradictions`
- `defaults_applied`

### Later Scoring

Consume:

- `structured_requirement.kpi_goals`
- `structured_requirement.budget_total`
- `structured_requirement.hard_constraints`
- `structured_requirement.preferred_constraints`
- `parse_status`

## Repo Mapping Summary

This contract does not replace `ShortlistRequirement`.

It wraps the existing repo object and adds:

- parser diagnostics
- explicit priority mapping
- failure semantics
- defaulting visibility

Backend engineers should build against `BriefParseInput` / `BriefParseOutput` first, then pass `structured_requirement` into existing shortlist planning and scoring code.
