# Xingtu Enrichment Record Schema

本文件定义 `xingtu-enrichment` 阶段需要补齐的字段结构。

## 一、前置条件字段

以下字段应已由 discovery 提供：

- `platform`
- `creator_name`
- `follower_count_raw`
- `persona_tags`
- `content_tags`
- `status`

只有满足以下条件的记录，才进入 enrichment：

1. 已有人设标签、内容标签
2. `xingtu_id` 为空
3. 记录未被标记为 `skipped` 或 `blocked`

---

## 二、星图身份字段

### xingtu_id
- 类型：string | null
- 说明：达人详情页 URL 中的 id 或页面展示 id

### xingtu_profile_url
- 类型：string | null

### xingtu_creator_type
- 类型：string | null
- 示例：
  - `颜值`
  - `美妆`
  - `生活`

### match_confidence
- 类型：string
- 枚举：
  - `high`
  - `medium`
  - `low`

### match_reason
- 类型：string | null
- 说明：用来解释为什么认为是同一达人

### search_name_used
- 类型：string
- 说明：本次实际搜索使用的达人名称/关键词

---

## 三、价格字段

### price_20s
- 类型：number | null
- 单位：人民币元

### price_20_60s
- 类型：number | null
- 单位：人民币元

### price_60s_plus
- 类型：number | null
- 单位：人民币元

---

## 四、效果字段

### estimated_play
- 类型：string | number | null
- 示例：
  - `50万+`
  - `500000`

### sponsored_median_play
- 类型：string | number | null

### natural_cpm
- 类型：number | null

### cpe
- 类型：number | null

### sponsored_completion_rate
- 类型：string | number | null
- 示例：
  - `35%`
  - `0.35`

---

## 五、趋势与人群字段

### monthly_fan_growth_rate
- 类型：string | number | null

### monthly_connected_user_fan_ratio
- 类型：string | number | null

### monthly_deep_user_fan_ratio
- 类型：string | number | null

---

## 六、其他补充字段

### recent_15_curve_screenshot_path
- 类型：string | null
- 说明：近 15 条播放曲线截图存储路径

### cooperate_brands
- 类型：string[] | null

### field_missing_list
- 类型：string[]
- 说明：记录哪些字段当前页面没有拿到

### enrichment_notes
- 类型：string | null

---

## 七、状态字段

### enrichment_status
- 类型：string
- 枚举：
  - `xingtu_completed`
  - `xingtu_not_found`
  - `xingtu_unregistered`
  - `ambiguous_match`
  - `field_partial`
  - `blocked`

### next_action
- 类型：string
- 枚举：
  - `done`
  - `manual_review`
  - `retry_later`

---

## 八、回填规则

只有当以下条件成立时，才允许回填到正式记录：

1. 匹配置信度不是 `low`
2. 达人身份校验通过
3. 至少拿到以下之一：
   - 星图 id
   - 星图主页链接
   - 达人类型
4. 如果是价格相关字段，必须来自同一达人详情页

若匹配不稳，则：
- 不回填价格
- 不回填商业表现
- 状态标记为 `ambiguous_match`