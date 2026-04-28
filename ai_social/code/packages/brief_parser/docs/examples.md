# Brief Parse Examples

These examples are business examples, not code fixtures.

## Example 1. Complete Brief

### Raw Business Input

```text
品牌：Lumiere
产品：双效精华液
SKU：LM-298
平台：抖音
城市：上海
预算：12 万
目标人群：25-35 岁一二线城市女性，白领，中高消费
KPI：播放量稳定、完播率、互动质量
内容方向：高级感、自然种草、护肤教程、生活方式 vlog
合规：必须标注 #广告，不能出现医疗词
必须：美妆达人，女性粉丝为主，同城优先
优先：近期开播活跃，做过护肤种草
可谈：可提供后台截图
```

### Expected Structured Business Output

**基础信息**

- brand: Lumiere
- product_name: 双效精华液
- product_sku: LM-298
- platform: 抖音
- city: 上海
- product_category: 美妆个护方向

**目标人群**

- 女性
- 25-35 岁方向
- 一二线城市
- 白领
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

**Hard Constraints / 红色**

- 美妆达人方向
- 女性粉丝为主
- 同城优先中如果被业务明确视为必要，则进入硬性；否则进入优先
- 必须标注 #广告
- 禁用医疗词

**Preferred Constraints / 绿色**

- 近期开播活跃
- 做过护肤种草

**Negotiable Constraints / 黄色**

- 可提供后台截图

**Diagnostics**

- missing: none
- ambiguity: none
- contradiction: none

### Why It Landed This Way

- 品牌 / 产品 / 预算 / 人群 / KPI / 风格 / 合规都比较完整，所以这是完整 brief。
- 红色信息直接来自“必须”和合规要求。
- 绿色信息来自“优先”表达。
- 黄色信息来自“可谈”表达。

## Example 2. Partially Incomplete Brief

### Raw Business Input

```text
品牌：North Harbor
产品：City Walk 防晒喷雾
平台：抖音
人群：女生通勤人群
内容方向：自然种草、生活方式
需要：生活方式或美妆达人
备注：先整理一版初筛名单
```

### Expected Structured Business Output

**基础信息**

- brand: North Harbor
- product_name: City Walk 防晒喷雾
- platform: 抖音
- product_category: 美妆 / 生活方式交叉方向

**目标人群**

- 女性
- 通勤生活场景

**内容方向**

- 自然种草
- 生活方式

**Hard Constraints / 红色**

- 生活方式或美妆达人方向

**Preferred Constraints / 绿色**

- 暂无明确绿色项，可保留为空

**Negotiable Constraints / 黄色**

- 先整理初筛名单

**Diagnostics**

- missing:
  - budget missing
  - KPI missing
  - compliance missing
  - geography missing
- ambiguity:
  - audience still broad
- contradiction: none

### Why It Landed This Way

- brief 足以给出初步方向，但不足以做高置信 shortlist。
- “需要”应视为偏硬性方向。
- “先整理一版初筛名单”更像阶段性备注，不应被误判为硬性筛选条件。

## Example 3. Ambiguous / Messy Brief

### Raw Business Input

```text
品牌：Velvet Lab
产品：可能是唇釉，也可能是精华线
平台：小红书或者抖音都行，maybe both
预算：5 万左右，看达人情况
人群：年轻女生都可以，学生和白领都能接受
KPI：数据别太差，最好互动强一点
风格：高级感，但也可以搞笑一点；自然，但最好有戏剧性
必须：美妆达人，但最好有宠物家庭氛围
避免：宠物内容
可谈：如果合适也可以直播合作
优先：上海或杭州，但其实别的城市也可以
```

### Expected Structured Business Output

**基础信息**

- brand: Velvet Lab
- product_name: uncertain between lip product and serum line
- platform: unclear between current in-scope and out-of-scope platform mix
- budget: approximate only

**目标人群**

- 年轻女性
- 学生 / 白领方向
- audience precision remains weak

**KPI / 目标**

- wants decent data
- wants stronger interaction
- no clean quantitative KPI

**Hard Constraints / 红色**

- 美妆达人方向

**Preferred Constraints / 绿色**

- 上海或杭州优先

**Negotiable Constraints / 黄色**

- 直播合作可能性

**Diagnostics**

- missing:
  - exact budget
  - exact KPI
  - compliance requirement
  - exact product focus
- ambiguity:
  - platform
  - budget
  - KPI
  - audience
  - style direction
- contradiction:
  - wants pet-family vibe but avoids pet content
- unsupported:
  - if the current V1 only supports the Douyin shortlist path, mixed-platform and live-stream asks remain out of scope

### Why It Landed This Way

- 这是典型“可读但不可直接执行”的 messy brief。
- 业务方向可以提取，但不能假装已经足够清晰。
- 应输出结构化 brief + 明确诊断，而不是强行给出高确定性 shortlist 输入。

## Example Reading Rule

These examples should be read as business interpretation examples:

- they show what information should be preserved
- they show how red / green / yellow should be understood
- they show how diagnostics should travel with the structured brief

They are not implementation fixtures and should not be mistaken for code schema or test cases.
