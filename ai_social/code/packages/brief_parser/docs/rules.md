# Brief Parse Rules

This file holds the compact business rules for `brief-parse`.

## A. Red / Green / Yellow Mapping

### Red

Red means:

- 必须满足
- 不满足直接影响 shortlist 合理性
- 应作为硬性底线处理

Typical red information:

- required product/category fit
- required audience fit
- platform limitation relevant to current workflow
- compliance restrictions
- exclusion rules
- must-have content direction
- explicit red-line KPI or delivery requirements

### Green

Green means:

- 优先满足
- 满足后提升推荐优先级
- 不满足不一定直接淘汰

Typical green information:

- preferred creator history
- preferred city or activation convenience
- recent growth
- prior seeding success
- preferred price band
- preferred activity rhythm

### Yellow

Yellow means:

- 可谈
- 可在 shortlist review 或建联前后再确认
- 当前不应直接作为淘汰条件

Typical yellow information:

- data return screenshots
- sample support
- script support
- exclusivity discussion
- backstage cooperation details

### Additional Rule

Even if a brief does not explicitly say red / green / yellow:

- compliance and exclusions should still be treated as red
- core category / audience / platform fit may still need to be treated as hard business conditions
- later-stage commercial coordination items should usually remain yellow unless the brief makes them hard blockers

## B. Normalization Rules

### Audience Normalization

Normalize audience text into reusable business traits:

- gender
- age direction
- city level
- lifestyle / role identity
- consumption level
- interest direction

Examples:

- `女白领` -> 女性 + 都市白领
- `轻熟肌中高消费女生` -> 女性 + 轻熟消费方向 + 精致消费方向
- `学生党` -> 年轻消费人群 or student-like audience direction

If the brief only says `泛人群`, keep it broad and mark ambiguity.

### Budget Normalization

Normalize budget into:

- total budget if available
- single-content expected range if explicitly stated
- budget confidence state

Rules:

- exact numeric budgets should be preserved as exact budget inputs
- range-style budgets should remain ranges or notes until product/backend decides how to store them
- vague phrasing like `预算看情况` should not be converted into fake precise values

### KPI Normalization

Normalize KPI text into shortlist-useful objective directions:

- 曝光 / 播放量
- 完播率
- 互动率 / 评论收藏质量
- 种草效率
- 口碑传播

Rules:

- explicit thresholds should be preserved as hard or preferred business signals
- general phrases like `效果好一点` should be marked ambiguous
- KPI should reflect business intent, not only numeric metrics

### Platform Normalization

Normalize platform information into the current workflow context.

Rules:

- if the brief clearly targets current V1 shortlist context, keep it in-scope
- if it mentions unsupported platforms or mixed-platform uncertainty, preserve that as unsupported or ambiguous rather than pretending support exists

### Geography Normalization

Normalize geography into:

- explicit city
- city level
- nationwide / unrestricted
- event-linked local requirement

Rules:

- same-city activation needs should stay visible
- if geography is absent, do not infer local restriction
- if geography is broad or contradictory, mark ambiguity

### Style / Tone Normalization

Normalize content language into:

- content form
- style tags
- tone tags
- must-have content elements

Examples:

- `高级感自然种草` -> tone/style direction
- `真实测评 / 生活方式 vlog` -> content form and scene direction
- `必须有产品特写` -> hard content requirement

## C. Missing / Ambiguity / Contradiction Rules

### Mark Missing Information When

The brief does not provide enough clarity on fields that materially affect shortlist quality.

High-priority missing items:

- brand or product
- target audience
- KPI direction
- budget
- category / creator direction

Review-priority missing items:

- compliance
- geography
- special coordination asks

### Mark Ambiguity When

The brief contains language that cannot be cleanly normalized into a reliable field.

Typical ambiguity signals:

- `看情况`
- `都可以`
- `差不多`
- `maybe`
- `around`
- `尽量`
- `效果好一点`

### Mark Contradiction When

Two instructions materially conflict.

Typical contradiction patterns:

- required category also appears in exclusion
- strict geography requirement plus “anywhere is fine”
- short-video-only requirement plus live-first requirement
- premium tone requirement plus strongly conflicting style requirement

### Ask For Human Review When

Human review should be required if:

- contradiction exists
- unsupported request exists
- too many core fields are missing
- ambiguity affects budget, KPI, platform, or category direction

## D. Scope Rules

`brief-parse` should produce a usable shortlist-input brief.

It should not:

- decide final creator fit
- score creators
- resolve all taxonomy debates
- silently remove unsupported requests
- overfit implementation to one temporary parser
