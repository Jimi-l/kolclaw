# Creator Discovery Record Schema

本文件定义 `creator-discovery` 阶段的标准输出结构。

## 一、记录级字段

### record_id
- 类型：string
- 说明：本地唯一记录 id
- 生成建议：`dy_<creator_name_slug>_<yyyymmdd>_<short_hash>`

### source_stage
- 类型：string
- 固定值：`creator-discovery`

### platform
- 类型：string
- 固定值：`douyin`

### status
- 类型：string
- 枚举：
  - `discovered`
  - `queued_for_xingtu`
  - `skipped`
  - `blocked`

---

## 二、视频基础字段

### collection_date
- 类型：string
- 格式：`YYYY/MM/DD`

### video_url
- 类型：string
- 说明：爆款视频完整链接

### publish_time_raw
- 类型：string
- 说明：页面原始显示值
- 示例：
  - `1天前`
  - `3月1日`

### publish_date_normalized
- 类型：string | null
- 格式：`YYYY-MM-DD`
- 说明：若可推断则填标准日期，否则为 null

### hotness_age_score
- 类型：string
- 枚举：
  - `100%`
  - `90%`
  - `80%`
  - `70%`
  - `60%`
  - `50%`

### total_interaction_text
- 类型：string
- 示例：`👍151.2万 💬1.4万 ↗️10.2万 ⭐12.6万`

### like_count_raw
- 类型：string | null

### comment_count_raw
- 类型：string | null

### favorite_count_raw
- 类型：string | null

### share_count_raw
- 类型：string | null

### ai_generated_flag
- 类型：boolean | null
- 说明：页面有“内容由AI生成”等标识时为 true

---

## 三、达人基础字段

### creator_name
- 类型：string

### follower_count_raw
- 类型：string
- 示例：`12.5万`

### follower_count_normalized
- 类型：number | null
- 示例：`125000`

### total_liked_count_raw
- 类型：string | null
- 说明：主页总获赞

### recommendation_video_position
- 类型：string | null
- 枚举：
  - `pinned`
  - `middle`
  - `unknown`

---

## 四、近期流量判断字段

### recommendation_video_like_raw
- 类型：string | null

### recent_video_like_1_raw
- 类型：string | null

### recent_video_like_2_raw
- 类型：string | null

### recent_video_like_3_raw
- 类型：string | null

### recent_3_avg_like_raw
- 类型：string | null

### traffic_trend
- 类型：string | null
- 枚举：
  - `昙花一现`
  - `流量波动`
  - `持续爆款`

### traffic_trend_reason
- 类型：string | null
- 说明：一句话解释为什么这么判定

---

## 五、标签字段

### persona_tags
- 类型：string[]
- 约束：最多 2 个

### content_tags
- 类型：string[]
- 约束：最多 2 个

### scene_tags
- 类型：string[]
- 约束：可多选，但应控制在 1-3 个核心场景

### ad_fit
- 类型：string | null
- 枚举：
  - `曝光植入型`
  - `产品种草型`
  - `两者皆可`

### custom_tags_log
- 类型：object[]
- 结构：

```json
[
  {
    "tag_name": "专科医生",
    "tag_category": "persona",
    "reason": "简介提及职业身份，且近期内容为专业知识输出"
  }
]
六、辅助字段
notes
类型：string | null
说明：可记录异常、补充判断、页面观察
duplicate_key
类型：string
生成建议：douyin::<creator_name_normalized>
next_action
类型：string
枚举：
queue_for_xingtu
skip
manual_review
七、最小合格输出

若一条 discovery 记录要进入后续流程，至少应具备：

platform
creator_name
video_url
collection_date
total_interaction_text
follower_count_raw
traffic_trend
persona_tags
content_tags
ad_fit
status

缺少上述关键字段时，不应直接进入 enrichment。


---
