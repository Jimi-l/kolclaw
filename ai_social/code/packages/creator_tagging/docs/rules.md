# Creator Tagging Rules

This file defines the business rules that translate a structured brief into shortlist-ready tag conditions.

## A. Mapping Rules

### 1. Audience -> Audience Match Tags

Structured brief audience information should map into audience-facing creator tags.

Translate:

- gender direction -> `audience:*`
- age direction -> `audience:*`
- city-level audience direction -> `audience:*` or `geography_fit_tags`
- consumption direction -> `audience:*`
- lifestyle role direction -> `audience:*` or `creator_profile_tags`

Examples:

- `女性` -> required or preferred audience tag depending on priority
- `都市白领` -> audience/work-life tag
- `精致消费人群` -> premium-consumption audience tag

### 2. Product / Category -> Creator Profile Tags

Product and category direction should map first into creator vertical and content vertical tags.

Examples:

- skincare / beauty -> `creator_vertical:beauty`
- fashion / outfit -> `creator_vertical:fashion`
- lifestyle scenario -> `creator_vertical:lifestyle`

Rule:

- in V1, favor high-utility vertical tags over long-tail taxonomy depth
- if exact taxonomy depth is unclear, keep a broad but usable creator-profile tag

### 3. Content Style / Tone -> Content Style Tags

Content style and tone should become shortlist-ready style tags, not scores.

Examples:

- `高级感` -> style/tone tag
- `自然种草` -> seeding-style tag
- `生活方式 vlog` -> content-format tag
- `真实测评` -> content-format / credibility tag

Rule:

- style direction should influence required or preferred tags depending on brief priority
- conflicting style directions should create review flags rather than false precision

### 4. Exclusions -> Exclusion Tags

Explicit avoid lists should become `exclusion_tags`.

Examples:

- `宠物` -> exclude pet content / pet creator direction
- `母婴` -> exclude parenting vertical when clearly out of scope

Rule:

- exclusions should remain visible as separate negative conditions
- exclusions should not be hidden inside general notes

### 5. Compliance -> Compliance Filter Tags

Compliance notes should become hard screening tags, not optional tags.

Examples:

- ad labeling required
- no medical claims
- sensitive-topic avoidance
- negative-publicity red line

Rule:

- compliance stays closer to hard filtering than to preference scoring
- if compliance wording is incomplete, create review flags rather than assuming “safe”

### 6. Geography -> Geography Fit Tags

City or geography direction should become regional fit tags.

Examples:

- `上海` -> city tag
- `一二线城市` -> city-level tag

Rule:

- same-city or activation-specific geography may become required or preferred depending on brief priority
- if geography is broad or contradictory, mark it for review

### 7. Platform -> Platform Scope Tags

Platform information defines tagging scope before creator tags are expanded.

Rule:

- V1 should only normalize in-scope platform tagging for the current shortlist flow
- mixed-platform requests should create review or out-of-scope notes rather than fake unified tagging

## B. Priority Rules

### Hard Constraints -> Required Tags

Structured brief hard constraints should usually become:

- `required_tags`
- `compliance_filter_tags`
- `exclusion_tags`

Typical examples:

- core vertical fit
- required audience fit
- mandatory content direction
- platform scope
- compliance red lines

### Preferred Constraints -> Preferred Tags

Structured brief preferred constraints should become:

- `preferred_tags`
- sometimes `search_direction_tags`
- sometimes `review_only_tags` if the condition is valuable but not reliably filterable

Typical examples:

- preferred city
- preferred creator history
- preferred style nuance
- preferred activity direction

### Negotiable Constraints -> Review-Only Tags

Structured brief negotiable constraints should usually become:

- `review_only_tags`
- sometimes `tagging_notes`

Typical examples:

- backstage screenshot expectations
- sample support
- script support
- coordination details

## C. V1 Normalization Rules

The cleaned taxonomy is much broader than what V1 should operationalize.

### Normalized In V1

V1 should directly normalize only the highest-utility branches:

- platform scope
- top-level creator vertical
- audience profile direction
- content format / style direction
- tone direction
- geography fit
- compliance / exclusion tags
- a small number of search-direction tags

Useful V1 content verticals include, at minimum:

- beauty / skincare / makeup direction
- fashion / outfit direction
- lifestyle / vlog direction
- parenting direction
- pet direction

### Left As Raw Notes In V1

These may remain as notes or review hints rather than formal structured tags:

- long-tail third- or fourth-level taxonomy nodes
- detailed occupation labels
- detailed relationship / 出镜关系 labels
- very specific interest micro-tags
- very specific scene variants when not critical to shortlist logic

### Deferred To Later Scoring Or Review

These should not be forced into `creator-tagging`:

- traffic-quality judgments
- commercial performance judgments
- price-level suitability
- recommendation grade
- match score
- detailed monetization logic

Those belong later in scoring or manual review, not requirement translation.

## D. Review Rules

### Produce `unresolved_tagging_gaps` When

- product/category direction is too broad
- audience direction is too broad
- style direction cannot be mapped cleanly
- taxonomy branch choice is unclear for V1

### Produce `human_review_flags` When

- contradiction exists between required and excluded directions
- compliance requirements are unclear
- platform scope is mixed or unsupported
- geography requirements conflict
- the brief asks for tags outside current V1 scope

### Produce Out-Of-Scope Notes When

- the request depends on cross-platform identity matching
- the request depends on live-stream-first tagging
- the request depends on deep commercial or historical performance tags at this stage

## E. Non-Goals

`creator-tagging` should not:

- score creators
- decide final shortlist ranking
- generate outreach
- infer unsupported platform data
- assume the full taxonomy is operationally usable in V1
- confuse taxonomy availability with execution readiness
