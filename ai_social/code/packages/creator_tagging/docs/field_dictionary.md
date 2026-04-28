# Creator Tagging Field Dictionary

This dictionary defines the shared business field vocabulary for `creator-tagging`.

It is intentionally readable by:

- backend
- product
- operations

It is not a code schema dump.

## Core Output Fields

### `required_tags`

- 中文说明：必选标签 / 硬性匹配标签
- Meaning: creator tags that express non-negotiable fit conditions
- Example value: `vertical:beauty`, `audience:female`
- Required: yes as an output section
- Can be empty: yes, but only when the brief itself is weak
- Source from structured brief: hard constraints, core category, core audience, platform, mandatory style/compliance signals
- Downstream usage: shortlist filtering and hard gating

### `preferred_tags`

- 中文说明：优先标签 / 加分标签
- Meaning: creator tags that improve fit but should not auto-block if absent
- Example value: `city:shanghai`, `creator_experience:skincare_seeding`
- Required: yes as an output section
- Can be empty: yes
- Source from structured brief: preferred constraints, softer audience/style/scene preferences
- Downstream usage: retrieval ranking and human review ordering

### `exclusion_tags`

- 中文说明：排除标签
- Meaning: creator directions or content types that should be avoided
- Example value: `exclude:pet_content`, `exclude:parenting`
- Required: yes as an output section
- Can be empty: yes
- Source from structured brief: exclusions, avoid lists, risk notes
- Downstream usage: hard filtering and contradiction checks

### `review_only_tags`

- 中文说明：仅供复核标签
- Meaning: business conditions that matter but should not yet become automatic filters
- Example value: `review:data_return_expected`
- Required: yes as an output section
- Can be empty: yes
- Source from structured brief: optional notes, negotiable asks, later-stage coordination details
- Downstream usage: shortlist review and later outreach preparation

### `search_direction_tags`

- 中文说明：搜索方向标签
- Meaning: tags used to guide search, retrieval phrasing, and manual scouting direction
- Example value: `search:高级感护肤`, `search:白领种草`
- Required: recommended
- Can be empty: yes if the brief is weak
- Source from structured brief: product category, audience, style, tone, geography, keyword direction
- Downstream usage: planning and retrieval guidance

### `audience_match_tags`

- 中文说明：人群匹配标签
- Meaning: tags that express desired follower profile direction
- Example value: `audience:female`, `audience:urban_white_collar`
- Required: recommended
- Can be empty: yes, but should trigger review
- Source from structured brief: target audience, hard/preferred audience constraints
- Downstream usage: shortlist review and later audience fit evaluation

### `content_style_tags`

- 中文说明：内容风格标签
- Meaning: normalized content expression, scenario, and style direction
- Example value: `content:lifestyle_vlog`, `style:premium`
- Required: recommended
- Can be empty: yes
- Source from structured brief: content style tags, tone tags, must-have content directions
- Downstream usage: retrieval guidance and creator-content fit review

### `creator_profile_tags`

- 中文说明：达人画像标签
- Meaning: profile-level creator direction tags that describe the kind of creator being sought
- Example value: `creator_vertical:beauty`, `creator_scene:office_life`
- Required: recommended
- Can be empty: yes
- Source from structured brief: product category, scene, audience, style, creator direction notes
- Downstream usage: search direction and manual review alignment

### `compliance_filter_tags`

- 中文说明：合规过滤标签
- Meaning: hard compliance signals that should not be treated as optional
- Example value: `compliance:ad_label_required`, `compliance:no_medical_claims`
- Required: recommended
- Can be empty: yes, but should trigger review
- Source from structured brief: compliance notes, risk notes, industry red lines
- Downstream usage: hard screening and manual risk review

### `unresolved_tagging_gaps`

- 中文说明：未解决的标签缺口
- Meaning: important tag mappings that could not be confidently translated
- Example value: `unclear_subcategory`, `audience_too_broad`
- Required: yes as an output section
- Can be empty: yes
- Source from structured brief: ambiguity, missing information, unsupported detail
- Downstream usage: tells backend and reviewers where the brief-to-tag mapping is incomplete

### `human_review_flags`

- 中文说明：人工复核标记
- Meaning: explicit flags that say tagging needs business or operational review
- Example value: `platform_ambiguous`, `brief_contradiction_present`
- Required: yes as an output section
- Can be empty: yes
- Source from structured brief: ambiguity, contradiction, unsupported requests
- Downstream usage: review workflow routing and UI explanation

## Supporting Tag Groups

### `platform_scope_tags`

- 中文说明：平台范围标签
- Meaning: tags that define which platform scope the tagging is being prepared for
- Example value: `platform:douyin`
- Required: recommended
- Can be empty: no for a clean V1 output
- Source from structured brief: platform
- Downstream usage: keeps retrieval and shortlist generation in the correct scope

### `geography_fit_tags`

- 中文说明：地域匹配标签
- Meaning: tags that express city or regional fit
- Example value: `city:shanghai`, `region:tier_1`
- Required: no
- Can be empty: yes
- Source from structured brief: city, regional restrictions, city-level audience direction
- Downstream usage: helps shortlist planning and same-city preference review

### `taxonomy_scope_notes`

- 中文说明：类目范围备注
- Meaning: notes about what taxonomy depth was actually used in this tagging output
- Example value: `used一级类目 + 部分二级类目，未展开长尾三级标签`
- Required: recommended
- Can be empty: yes
- Source from tagging interpretation
- Downstream usage: helps backend and ops avoid over-reading taxonomy coverage

### `tagging_notes`

- 中文说明：标签说明
- Meaning: explanatory notes about how the brief was translated into tags
- Example value: `同城优先保留为 preferred，不升级为 hard filter`
- Required: no
- Can be empty: yes
- Source from business interpretation
- Downstream usage: reviewer explanation and product/backend alignment
