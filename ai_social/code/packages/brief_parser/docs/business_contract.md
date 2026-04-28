# Brief Parse Business Contract

## Canonical Status

This document set is the canonical business-spec source for `brief-parse` in the current phase.

The following files may exist elsewhere in the repo as implementation drafts:

- `apps/api/app/schemas/brief_parse.py`
- `apps/api/app/services/brief_parse_interface.py`
- `packages/common/schemas/brief_parse_*.schema.json`
- `apps/api/tests/fixtures/brief_parse/*`

Those artifacts are not the primary source of truth for this documentation pass.
For this phase, backend, product, and operations should align on the markdown contract files in `docs/contracts/`.

## A. Module Purpose

`brief-parse` is the business stage that turns raw campaign input into a structured brief that later shortlist logic can consume.

It sits at the front of the current V1 pipeline:

`raw brief -> brief-parse -> structured shortlist requirement -> search planning / manual scouting / shortlist review`

It is responsible for:

- extracting business facts from raw input
- organizing those facts into stable structured fields
- identifying red / green / yellow priority
- surfacing missing information
- surfacing ambiguity and contradiction
- preserving enough context for downstream shortlist work

It is not responsible for:

- finding creators
- ranking creators
- querying Xingtu
- drafting outreach
- sending anything externally

## B. Input Description

`brief-parse` accepts business input in messy real-world forms, including:

- raw brand brief text
- meeting notes
- chat transcript
- manually整理后的 brief 信息
- copied table rows or partial requirement lists

### Minimum Useful Information

At business level, the parser becomes meaningfully useful when it can identify most of the following:

- brand or campaign identity
- product or promoted item
- target audience
- campaign goal or KPI direction
- content category or creator direction

If budget, compliance, or geography are missing, parsing can still continue, but the output should clearly stay partial.

### Optional Information

The parser may also receive:

- SKU
- competitor notes
- posting timeline
- content must-have elements
- prior投放经验
- backstage data return requirements
- platform preference
- regional restrictions
- exclusivity or script/sample requirements

These should be preserved when relevant, but not all of them need to be hard-coded into the first repo structure.

### When Information Is Missing

If information is missing, `brief-parse` should not fail silently.
It should still produce a structured brief, but it must also mark:

- what is missing
- whether the gap blocks search or only weakens confidence
- whether a human should confirm before downstream use

## C. Output Description

The output of `brief-parse` is a **structured brief** for shortlist work.

A structured brief means:

- the business ask has been decomposed into stable fields
- fields are organized by downstream use, not by source phrasing
- hard constraints are separated from preferences and negotiable items
- known gaps and risks are preserved, not hidden

### Core Output Sections

The structured business output should contain at least:

1. campaign identity
2. product and category direction
3. audience definition
4. KPI and objective direction
5. content style and tone
6. budget and commercial limits
7. geography / region
8. compliance and exclusion rules
9. derived search-direction keywords
10. priority classification
11. diagnostics

### Constraint Representation

The business output should distinguish three levels:

- hard constraints
  items that should block candidate acceptance if not met
- preferred constraints
  items that improve recommendation quality but do not automatically block
- negotiable constraints
  items that can be confirmed later or discussed during review / outreach

### Diagnostic Information To Preserve

The parser should preserve:

- missing information
- ambiguous wording
- contradictory instructions
- unsupported requests relative to current V1 scope
- defaults or assumptions that were applied

This diagnostic layer is part of the business output, not a debugging afterthought.

## D. Processing Logic

The business logic should be understood as the following sequence:

### Step 1. Extract brief facts

Read the input and identify business facts from the workflow source doc, especially:

- 品牌 & 产品信息
- 目标人群画像
- 投放目标 & KPI
- 预算区间
- 内容调性 & 风格
- 历史投放数据
- 时间节点 & 周期
- 合规 & 避坑要求
- 特殊需求
- 其他补充

### Step 2. Normalize into structured buckets

Convert the extracted facts into stable brief fields that downstream shortlist work can use consistently.

Examples:

- brand/product text -> campaign identity fields
- audience prose -> normalized audience traits
- KPI prose -> normalized objective/KPI fields
- budget prose -> budget section
- style/tone prose -> content style and tone section
- avoid lists / compliance notes -> risk and exclusion section

### Step 3. Classify priority

Interpret business priority using the workflow document’s color system:

- red = must satisfy
- green = prioritize if possible
- yellow = can negotiate later

Then map that into the structured brief as:

- hard constraints
- preferred constraints
- negotiable constraints

### Step 4. Identify missing information

Check whether critical business fields are absent or weakly specified.
At minimum, review:

- product
- target audience
- KPI direction
- budget
- content category / creator direction
- compliance requirements

### Step 5. Identify ambiguity and contradiction

If input wording is vague, mixed, or self-conflicting, preserve the issue explicitly.

Examples:

- “预算看情况”
- “平台都可以”
- “希望上海，但其实哪里都行”
- “要宠物达人，但避免宠物内容”

### Step 6. Generate downstream-ready shortlist requirement info

Prepare the output so later modules can consume it directly for:

- search direction
- scouting checklist
- tag alignment
- shortlist review
- later scoring inputs

## E. Edge Cases

### Incomplete Brief

Example:

- no budget
- no city
- no compliance notes

Business output:

- still return a structured brief
- mark the relevant fields as missing
- classify the brief as partial rather than complete

### Contradictory Brief

Example:

- asks for a creator type
- excludes the same creator type

Business output:

- preserve both signals
- mark contradiction explicitly
- require human review before downstream use

### Vague Audience

Example:

- “年轻女生都可以”
- “泛人群”

Business output:

- keep broad audience phrasing in normalized form if possible
- mark audience definition as ambiguous
- avoid pretending precise audience fit exists

### Unclear KPI

Example:

- “效果好一点”
- “数据不要太差”

Business output:

- preserve the goal direction if inferable
- mark KPI definition as ambiguous or missing
- do not invent specific thresholds

### Missing Budget

Business output:

- keep budget-related fields empty
- mark budget as missing
- allow planning to continue only in a partial state

### Missing Compliance Requirements

Business output:

- keep compliance section empty or minimal
- mark compliance review as still needed
- do not assume “no restrictions”

### Unsupported Requests

Examples relative to current V1:

- platform requests outside the current shortlist scope
- requests that mainly describe live-stream execution rather than short-video shortlist work

Business output:

- preserve the request as an unsupported item
- do not silently drop it
- do not pretend current V1 fully supports it

## F. Handoff Note For Backend

Backend should use this business contract to decide:

- which fields to persist as stable brief fields
- which fields to preserve as notes or diagnostics
- which fields should block downstream usage
- which fields can remain optional in V1

Backend should persist:

- the structured brief itself
- constraint buckets
- keyword direction
- diagnostics
- parsing status / confidence state

Downstream services should consume:

- structured fields for planning and review
- constraint buckets for filtering logic
- diagnostics for human review and UI explanation

Operations / product should remain able to edit:

- priority interpretation rules
- field vocabulary
- category taxonomy usage
- what counts as blocking vs. review-only missing info

These should not be hard-coded too early:

- long-tail taxonomy decisions
- all audience label dictionaries
- all compliance mappings
- all ambiguous-language resolution rules

Those areas should stay business-editable and be refined with real usage.
