# Creator Tagging Business Contract

## Canonical Status

This document set is the canonical business-spec source for `creator-tagging` in the current phase.

It should be read together with:

- `packages/brief_parser/docs/business_contract.md`
- `packages/brief_parser/docs/field_dictionary.md`
- `external_docs/operational/KOLclaw_媒介执行workflow_codex.md`
- `external_docs/operational/KolClaw_达人标签_codex.md`

If repo implementation drafts appear elsewhere later, they should follow this business contract rather than replace it.

## A. Purpose

`creator-tagging` is the business stage that translates a structured brief into shortlist-ready tagging conditions.

It sits after `brief-parse`:

`brief-parse -> creator-tagging -> shortlist generation / review / later scoring`

Its job is to answer:

- what kinds of creator tags should be treated as required
- what kinds of creator tags should be treated as preferred
- what should be excluded
- what should remain review-only
- what search-direction tags should guide manual or semi-structured retrieval

It is different from scoring:

- `creator-tagging` translates requirements into tagging conditions
- scoring later judges how well a specific creator matches those conditions

`creator-tagging` does not:

- score creators
- rank creators
- decide the final shortlist
- generate outreach
- fetch platform data

## B. Inputs

`creator-tagging` consumes the structured brief produced by `brief-parse`, especially:

- category / product direction
- target audience direction
- KPI direction where it affects tag emphasis
- content style and tone direction
- platform scope
- geography / city limitations
- exclusions
- compliance notes
- optional collaboration asks
- hard / preferred / negotiable constraint buckets

### Input Concepts

At business level, the most important incoming concepts are:

1. product-category direction
2. target audience direction
3. content style direction
4. tone direction
5. platform scope
6. geography fit
7. hard exclusions
8. compliance restrictions
9. optional or negotiable asks

### What Creator-Tagging Should Ignore Or Delay

Some structured brief fields should not immediately become creator tags in V1:

- exact budget arithmetic
- detailed price suitability
- historical commercial performance judgments
- growth-quality scoring
- traffic-quality scoring

Those belong later in shortlist review or scoring, not here.

## C. Outputs

The output of `creator-tagging` is a structured tagging package that downstream shortlist logic can consume.

### Core Output Concepts

The tagging package should include:

#### `required_tags`

Tags that represent non-negotiable creator-fit conditions.

Examples:

- `platform:douyin`
- `vertical:beauty`
- `audience:female`
- `content_style:seeding`

#### `preferred_tags`

Tags that improve shortlist quality but should not block inclusion on their own.

Examples:

- `city:shanghai`
- `audience:premium_consumption`
- `creator_experience:skincare_seeding`

#### `exclusion_tags`

Tags or creator directions that should be filtered out or explicitly avoided.

Examples:

- `exclude:pet_content`
- `exclude:parenting`
- `exclude:medical_claim_risk`

#### `review_only_tags`

Business signals that should be visible to shortlist reviewers but not turned into hard filters yet.

Examples:

- `review:data_return_expected`
- `review:sample_support_discussable`
- `review:script_support_possible`

#### `search_direction_tags`

Tags used to guide retrieval, scouting, or search phrasing.

Examples:

- `search:高级感护肤`
- `search:白领种草`
- `search:生活方式护肤`

#### `audience_match_tags`

Audience-facing tags that express the intended fan profile direction.

Examples:

- `audience:female`
- `audience:urban_white_collar`
- `audience:high_consumption`

#### `content_style_tags`

Normalized content-format or expression tags that help shortlist generation.

Examples:

- `content:beauty_review`
- `content:lifestyle_vlog`
- `style:premium`
- `style:natural_seeding`

#### `creator_profile_tags`

Profile-level creator direction tags, not performance scores.

Examples:

- `creator_vertical:beauty`
- `creator_vertical:lifestyle`
- `creator_scene:office_life`

#### `compliance_filter_tags`

Compliance-related tags that should be treated as hard screening signals.

Examples:

- `compliance:ad_label_required`
- `compliance:no_medical_claims`

#### `unresolved_tagging_gaps`

Tagging needs that could not be cleanly translated from the brief.

Examples:

- unclear product subcategory
- ambiguous audience direction
- incomplete geography scope

#### `human_review_flags`

Flags that tell shortlist reviewers where business confirmation is still needed.

Examples:

- platform ambiguity
- contradiction between desired vibe and excluded content
- unsupported live-stream requirement

## D. Position In Pipeline

The intended relationship is:

`brief-parse`
  turns messy business input into a structured brief

`creator-tagging`
  turns the structured brief into shortlist-ready tag conditions

`shortlist generation / review`
  uses those tag conditions to organize retrieval, filtering, and later matching work

`later scoring`
  evaluates how well an actual creator matches the conditions

Important distinction:

- `creator-tagging` is requirement translation
- it is not creator selection itself

## E. V1 Boundary

### In Scope For V1

- Douyin-focused creator tagging
- short-video creator direction tagging
- category, audience, style, tone, geography, exclusion, and compliance translation
- a limited set of operationally useful taxonomy branches
- review flags for unsupported or ambiguous asks

### Not In Scope For V1

- cross-platform identity linking
- full small-red-book / multi-platform normalized tagging
- live-stream-first tagging logic
- deep commercial performance tagging
- automated long-tail taxonomy normalization across the entire giant taxonomy
- turning every taxonomy branch into a structured runtime field

### V1 Principle

V1 should use a **small usable taxonomy subset**, not force all cleaned taxonomy content into immediate structured use.

## F. Backend Handoff Note

Backend should persist:

- required tags
- preferred tags
- exclusion tags
- review-only tags
- search-direction tags
- unresolved tagging gaps
- human review flags

Downstream shortlist generation should consume directly:

- required tags
- preferred tags
- exclusion tags
- compliance filter tags
- audience match tags
- search-direction tags

The following should remain editable by ops/product:

- which taxonomy branches are active in V1
- how broad audience language is normalized
- which review-only signals later graduate into preferred or required tags
- which compliance themes become standard hard filters

The following should remain explanatory only for now:

- long-tail occupation tags
- long-tail interest/lifestyle relationships
- deep monetization and performance tags
- visual trend / chart interpretation tags

The business goal of this module is not to maximize taxonomy coverage.
It is to create a stable, shortlist-ready requirement translation layer.
