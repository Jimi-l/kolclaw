# Creator Tagging Examples

These are business examples, not code fixtures.

## Example 1. Clear Beauty / Skincare Brief

### Input Structured Brief

**基础信息**

- brand: Lumiere
- product_name: 双效精华液
- product_category: 美妆个护 / 护肤方向
- platform: 抖音
- city: 上海

**目标人群**

- 女性
- 一二线城市
- 都市白领
- 中高消费

**KPI / 目标**

- 稳定播放
- 完播率
- 互动质量

**内容方向**

- 高级感
- 自然种草
- 护肤教程
- 生活方式 vlog

**Hard Constraints**

- 美妆达人方向
- 女性粉丝为主
- 合规要求必须满足

**Preferred Constraints**

- 上海优先
- 做过护肤种草
- 近期开播活跃

**Negotiable Constraints**

- 可提供后台截图

### Expected Tagging Output

**Required Tags**

- `platform:douyin`
- `creator_vertical:beauty`
- `audience:female`
- `content:skincare_review`
- `style:natural_seeding`

**Preferred Tags**

- `city:shanghai`
- `audience:urban_white_collar`
- `audience:premium_consumption`
- `creator_experience:skincare_seeding`
- `style:premium`

**Exclusion Tags**

- none explicitly beyond compliance restrictions

**Compliance Filter Tags**

- `compliance:ad_label_required`
- `compliance:no_medical_claims`

**Review-Only Tags**

- `review:data_return_expected`

**Search-Direction Tags**

- `search:高级感护肤`
- `search:白领护肤种草`
- `search:生活方式护肤`

**Unresolved Gaps**

- none major

### Why It Landed This Way

- 产品类目清晰，所以 creator vertical 可以直接落到 beauty/skincare 方向。
- audience 中的女性、白领、中高消费应转成 audience match tags，而不是只保留成文字说明。
- 后台截图是协作要求，不应升级为 required tag。

## Example 2. Incomplete But Usable Brief

### Input Structured Brief

**基础信息**

- brand: North Harbor
- product_name: City Walk 防晒喷雾
- product_category: 美妆 / 生活方式交叉方向
- platform: 抖音
- city: 未明确

**目标人群**

- 女性
- 通勤生活场景

**KPI / 目标**

- 未明确

**内容方向**

- 自然种草
- 生活方式

**Hard Constraints**

- 生活方式或美妆达人方向

**Preferred Constraints**

- 无明确优先项

**Negotiable Constraints**

- 先出一版初筛名单

### Expected Tagging Output

**Required Tags**

- `platform:douyin`
- `creator_vertical:beauty_or_lifestyle`
- `audience:female`
- `scene:commuter_life`
- `style:natural_seeding`

**Preferred Tags**

- none explicit

**Exclusion Tags**

- none explicit

**Review-Only Tags**

- `review:first_pass_shortlist_only`

**Search-Direction Tags**

- `search:通勤女生`
- `search:生活方式防晒`
- `search:自然种草`

**Unresolved Tagging Gaps**

- KPI direction missing
- exact audience precision still weak
- geography scope missing

**Human Review Flags**

- `review_missing_kpi`
- `review_missing_geography`

### Why It Landed This Way

- 这个 brief 仍然足够支持第一轮 tagging，因为平台、产品方向、基础 audience、内容方向都存在。
- 但 KPI 和 geography 还不够清晰，所以输出必须带 unresolved gaps。
- “先出一版初筛名单”是流程说明，不是 creator-fit hard tag。

## Example 3. Ambiguous Or Mixed-Signal Brief

### Input Structured Brief

**基础信息**

- brand: Velvet Lab
- product_name: 唇釉 or 精华线，尚未确定
- platform: 抖音 / 小红书混合表达
- city: 上海或杭州优先，但别的城市也行

**目标人群**

- 年轻女生
- 学生 / 白领都可以

**KPI / 目标**

- 数据别太差
- 希望互动强一点

**内容方向**

- 高级感
- 也可以搞笑
- 自然
- 也希望戏剧性

**Hard Constraints**

- 美妆达人

**Preferred Constraints**

- 上海或杭州优先

**Negotiable Constraints**

- 如果合适可直播合作

**Exclusions**

- 避免宠物内容

### Expected Tagging Output

**Required Tags**

- `creator_vertical:beauty`

**Preferred Tags**

- `city:shanghai`
- `city:hangzhou`

**Exclusion Tags**

- `exclude:pet_content`

**Review-Only Tags**

- `review:livestream_request_present`
- `review:style_conflict_present`

**Search-Direction Tags**

- `search:年轻女生美妆`
- `search:互动向美妆内容`

**Unresolved Tagging Gaps**

- exact product subcategory unclear
- platform scope mixed
- style direction internally conflicting
- KPI direction too weak for strong tag emphasis

**Human Review Flags**

- `review_platform_scope_ambiguous`
- `review_product_subcategory_ambiguous`
- `review_style_conflict`
- `review_live_request_out_of_scope_for_v1`

### Why It Landed This Way

- `美妆达人` still gives one clear creator vertical, so tagging should not collapse completely.
- But mixed platform scope, messy KPI wording, and conflicting style direction mean most nuance should remain review-led rather than over-structured.
- Live-stream cooperation should not be turned into a V1 operational tag condition.
