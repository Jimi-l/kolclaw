# Brief Parse Field Dictionary

This dictionary defines the shared business field vocabulary for `brief-parse`.

It is intentionally human-readable.
It is not a code schema dump.

## Field List

### `brand`

- 中文说明：品牌名称
- Meaning: the brand or campaign owner behind the brief
- Example: `Lumiere`
- Required: yes for a complete brief
- Can be empty: yes, but only in a partial brief
- Source from brief: brand name, client name, campaign owner line
- Downstream note: used to anchor campaign context and review output

### `product_name`

- 中文说明：产品名称 / 推广品名
- Meaning: the specific product, line, or promoted item
- Example: `双效精华液`
- Required: yes for a complete brief
- Can be empty: yes, but only in a partial brief
- Source from brief: product line, item name, promoted SKU family
- Downstream note: central for keyword generation and category alignment

### `product_sku`

- 中文说明：SKU / 型号 / 具体货号
- Meaning: the more specific product identifier when the brief includes it
- Example: `LM-298`
- Required: no
- Can be empty: yes
- Source from brief: SKU, 型号, 货号
- Downstream note: useful when product line has multiple variants

### `product_category`

- 中文说明：产品类目 / 达人方向类目
- Meaning: the primary content/category direction implied by the product and brief
- Example: `美妆`
- Required: strongly recommended
- Can be empty: yes, but should be flagged
- Source from brief: product description, content direction, category wording
- Downstream note: used by scouting, tagging, and shortlist planning

### `platform`

- 中文说明：投放平台
- Meaning: the platform context intended by the brief
- Example: `douyin`
- Required: yes for clean execution, but current V1 may default if absent
- Can be empty: business-wise no, parser-wise yes
- Source from brief: platform line, channel instructions, execution context
- Downstream note: unsupported platforms should be surfaced explicitly

### `city`

- 中文说明：城市 / 地域限制
- Meaning: target city or region if the brief has local constraints
- Example: `shanghai`
- Required: no
- Can be empty: yes
- Source from brief: city, region, local event location, same-city preference
- Downstream note: if empty, downstream should not assume nationwide or local automatically

### `target_audience`

- 中文说明：目标人群
- Meaning: normalized audience traits extracted from the brief
- Example: `女性`, `都市白领`, `精致消费人群`
- Required: yes for a strong shortlist brief
- Can be empty: yes, but should be marked missing
- Source from brief: audience profile, age, gender, city level, lifestyle, consumption level
- Downstream note: should drive creator audience fit and tag alignment

### `kpi_goals`

- 中文说明：投放目标 / KPI 方向
- Meaning: normalized campaign objectives and KPI emphasis
- Example: `播放量稳定`, `完播率`, `互动质量`
- Required: yes for a complete brief
- Can be empty: yes, but should be marked missing
- Source from brief: KPI line, objective line, “要曝光 / 要种草 / 要互动”
- Downstream note: later scoring and shortlist review depend on this heavily

### `budget_total`

- 中文说明：总预算
- Meaning: overall budget range or total budget for the campaign
- Example: `120000`
- Required: yes for a complete shortlist brief
- Can be empty: yes, but should be marked missing
- Source from brief: budget line, total budget statement
- Downstream note: supports budget reasoning and shortlist feasibility

### `content_style_tags`

- 中文说明：内容风格标签
- Meaning: normalized content expression and format style
- Example: `种草`, `教程感`, `高级感`
- Required: recommended
- Can be empty: yes
- Source from brief: style, content form, scene,植入方式
- Downstream note: guides content-fit interpretation

### `tone_tags`

- 中文说明：调性标签
- Meaning: normalized campaign tone or brand feeling
- Example: `可信`, `精致感`
- Required: recommended
- Can be empty: yes
- Source from brief: tone, overall feeling, brand direction
- Downstream note: useful in creator selection and later outreach adaptation

### `compliance_notes`

- 中文说明：合规与避坑要求
- Meaning: restrictions, red lines, ad-labeling needs, sensitivity constraints
- Example: `必须标注#广告`, `不能出现医疗词`
- Required: recommended for safe execution
- Can be empty: yes, but should trigger follow-up
- Source from brief: compliance section, avoid list, category restrictions
- Downstream note: should be treated as red-line review information

### `exclusions`

- 中文说明：排除项
- Meaning: creator types, content types, themes, or risks that should be avoided
- Example: `宠物`, `母婴`
- Required: no
- Can be empty: yes
- Source from brief: avoid, exclude, 不要, 排除
- Downstream note: should feed hard filtering and contradiction review

### `optional_notes`

- 中文说明：可谈项 / 备注
- Meaning: business asks that are useful but not necessarily blocking
- Example: `可提供后台数据截图`
- Required: no
- Can be empty: yes
- Source from brief: note, optional,可选,可协商
- Downstream note: typically stays negotiable unless later elevated

### `keywords`

- 中文说明：搜索方向关键词
- Meaning: search-direction phrases derived from the brief rather than copied verbatim
- Example: `高级感轻熟肌`, `白领护肤分享`
- Required: recommended
- Can be empty: yes in a weak brief
- Source from brief: derived from product, audience, tone, KPI, category
- Downstream note: supports planning and manual scouting direction

## Constraint Bucket Fields

### `hard_constraints`

- 中文说明：硬性条件
- Meaning: conditions that should be treated as red-line filters
- Example content: required category, must-have audience direction, geography limits, compliance red lines
- Required: yes as a section
- Can be empty: yes in a weak brief, but not ideal
- Source from brief: red items, must lines, compliance restrictions, blocking requirements
- Downstream note: primary shortlist gating input

### `preferred_constraints`

- 中文说明：优先条件
- Meaning: conditions that should improve ranking but not automatically block
- Example content: recent growth, prior seeding experience, preferred city, active posting rhythm
- Required: yes as a section
- Can be empty: yes
- Source from brief: green items, prefer lines,优先项
- Downstream note: useful for planning, ranking, and review ordering

### `negotiable_constraints`

- 中文说明：可谈条件
- Meaning: later-stage business asks that do not need to block the shortlist now
- Example content:后台数据截图,试用装,脚本支持
- Required: yes as a section
- Can be empty: yes
- Source from brief: yellow items, optional lines,可谈项
- Downstream note: should be visible for review and future outreach but not over-hardened

## Diagnostic Fields

### `missing_information`

- 中文说明：缺失信息
- Meaning: business fields that were not present or not recoverable
- Example: `budget missing`
- Required: yes as a section
- Can be empty: yes
- Source from brief: inferred by completeness check
- Downstream note: should support review workflow and requirement补全

### `ambiguities`

- 中文说明：模糊信息
- Meaning: vague wording that cannot be cleanly normalized without review
- Example: `预算看情况`, `平台都可以`
- Required: yes as a section
- Can be empty: yes
- Source from brief: ambiguous phrasing
- Downstream note: should block overconfident automation

### `contradictions`

- 中文说明：矛盾信息
- Meaning: conflicting instructions inside the same brief
- Example: `要宠物达人` + `避免宠物`
- Required: yes as a section
- Can be empty: yes
- Source from brief: conflicting requirements
- Downstream note: should trigger human review

### `unsupported_requests`

- 中文说明：超出当前范围的需求
- Meaning: requests that current V1 shortlist scope cannot properly handle
- Example: unsupported platform, live-stream-first requirement
- Required: yes as a section
- Can be empty: yes
- Source from brief: out-of-scope requests
- Downstream note: should be shown clearly instead of silently dropped

### `defaults_or_assumptions`

- 中文说明：默认值 / 假设
- Meaning: fallback interpretation applied because the brief did not fully specify something
- Example: platform defaulted to Douyin-compatible shortlist context
- Required: recommended
- Can be empty: yes
- Source from brief + parser policy
- Downstream note: keeps backend and operations aligned on what was inferred vs. stated
