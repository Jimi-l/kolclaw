# Fields

本文档定义首版字段，并明确哪条 workflow 负责填充哪些字段。

---

## 1. Record Levels

首版数据分为三层：

1. `VideoCandidate`
   - 描述推荐流里发现的一条潜力视频
2. `CreatorRecord`
   - 描述一个达人基础记录，承载 discovery 结果，并可附加星图补充结果
3. `XingtuRecord`
   - 描述星图侧商业化字段

---

## 2. Discovery-Owned Fields

以下字段由 `Douyin discovery workflow` 负责：

| Field | Model | Meaning | Filled By |
|------|------|---------|-----------|
| `capture_date` | `VideoCandidate` | 采集日期 | Douyin discovery |
| `video_url` | `VideoCandidate` | 爆款视频链接 | Douyin discovery |
| `publish_date` | `VideoCandidate` | 归一化发布时间 | Douyin discovery |
| `publish_time_text` | `VideoCandidate` | 页面原始发布时间文本 | Douyin discovery |
| `freshness_score` | `VideoCandidate` | 爆款时效分值 | Douyin discovery |
| `like_count` | `VideoCandidate` | 点赞数 | Douyin discovery |
| `comment_count` | `VideoCandidate` | 评论数 | Douyin discovery |
| `share_count` | `VideoCandidate` | 转发数 | Douyin discovery |
| `favorite_count` | `VideoCandidate` | 收藏数 | Douyin discovery |
| `total_interaction_text` | `VideoCandidate` | 互动摘要字符串 | Douyin discovery |
| `creator_name` | `VideoCandidate` / `CreatorRecord` | 达人昵称 | Douyin discovery |
| `follower_count` | `VideoCandidate` / `CreatorRecord` | 粉丝量 | Douyin discovery |
| `ai_generated_flag` | `VideoCandidate` | 是否出现 AI 生成标识 | Douyin discovery |
| `profile_url` | `CreatorRecord` | 达人主页链接 | Douyin discovery |
| `total_likes` | `CreatorRecord` | 达人主页总获赞 | Douyin discovery |
| `recommended_video_position` | `CreatorRecord` | 推荐视频位于置顶或中间 | Douyin discovery |
| `recommended_video_like_count` | `CreatorRecord` | 推荐视频点赞数 | Douyin discovery |
| `recent_video_like_counts` | `CreatorRecord` | 最新 3 条视频点赞数 | Douyin discovery |
| `recent_video_average_like_count` | `CreatorRecord` | 最新 3 条平均点赞 | Douyin discovery |
| `traffic_trend` | `CreatorRecord` | 流量趋势判断 | Douyin discovery |
| `persona_tags` | `CreatorRecord` | 人设标签，最多 2 个 | Douyin discovery |
| `content_tags` | `CreatorRecord` | 内容标签，最多 2 个 | Douyin discovery |
| `scene_tags` | `CreatorRecord` | 内容关键场景 | Douyin discovery |
| `ad_fit` | `CreatorRecord` | 广告类型适配 | Douyin discovery |
| `analysis_notes` | `CreatorRecord` | 分析备注 / 新增标签说明 | Douyin discovery |
| `enrichment_status` | `CreatorRecord` | 星图补数状态，初始一般为 `pending` | Douyin discovery |

---

## 3. Xingtu-Owned Fields

以下字段由 `Xingtu enrichment workflow` 负责：

| Field | Model | Meaning | Filled By |
|------|------|---------|-----------|
| `xingtu_id` | `XingtuRecord` | 星图达人 ID | Xingtu enrichment |
| `creator_types` | `XingtuRecord` | 星图达人类型标签 | Xingtu enrichment |
| `profile_url` | `XingtuRecord` | 星图主页链接 | Xingtu enrichment |
| `price_20s` | `XingtuRecord` | 20s 星图价 | Xingtu enrichment |
| `price_20_to_60s` | `XingtuRecord` | 20-60s 星图价 | Xingtu enrichment |
| `price_60s_plus` | `XingtuRecord` | 60s+ 星图价 | Xingtu enrichment |
| `estimated_play_volume` | `XingtuRecord` | 预估播放量 | Xingtu enrichment |
| `sponsored_play_median` | `XingtuRecord` | 商单播放量中位数 | Xingtu enrichment |
| `organic_cpm` | `XingtuRecord` | 自然量 CPM | Xingtu enrichment |
| `cpe` | `XingtuRecord` | CPE | Xingtu enrichment |
| `completion_rate` | `XingtuRecord` | 商单完播率 | Xingtu enrichment |
| `play_curve_screenshot` | `XingtuRecord` | 近 15 条播放曲线截图路径 | Xingtu enrichment |
| `monthly_follower_growth_rate` | `XingtuRecord` | 月涨粉率 | Xingtu enrichment |
| `connected_user_fan_ratio` | `XingtuRecord` | 月连接用户粉丝比 | Xingtu enrichment |
| `deep_user_fan_ratio` | `XingtuRecord` | 月深度用户粉丝比 | Xingtu enrichment |
| `cooperative_clients` | `XingtuRecord` | 合作客户列表 | Xingtu enrichment |
| `match_status` | `XingtuRecord` | `pending/complete/partial/not_found/not_registered` | Xingtu enrichment |
| `notes` | `XingtuRecord` | 缺失字段 / 匹配说明 | Xingtu enrichment |

---

## 4. Shared / System Fields

以下字段由系统或 shared layer 维护：

| Field | Model | Meaning | Filled By |
|------|------|---------|-----------|
| `record_id` | `CreatorRecord` | 本地唯一记录 ID | System |
| `platform` | `CreatorRecord` | 当前默认 `douyin` | System / discovery |
| `created_at` | `CreatorRecord` | 记录创建时间 | Storage |
| `updated_at` | `CreatorRecord` | 最近更新时间 | Storage |
| `workflow_name` | `WorkflowSummary` | workflow 名称 | Workflow |
| `status` | `WorkflowSummary` | run 状态 | Workflow |
| `started_at` | `WorkflowSummary` | 开始时间 | Workflow |
| `finished_at` | `WorkflowSummary` | 结束时间 | Workflow |
| `duration_seconds` | `WorkflowSummary` | 执行时长 | Workflow |
| `processed_count` | `WorkflowSummary` | 处理数量 | Workflow |
| `created_count` | `WorkflowSummary` | 新建数量 | Workflow |
| `updated_count` | `WorkflowSummary` | 更新数量 | Workflow |
| `skipped_count` | `WorkflowSummary` | 跳过数量 | Workflow |
| `error_count` | `WorkflowSummary` | 错误数量 | Workflow |
| `notes` | `WorkflowSummary` | 摘要备注 | Workflow |

---

## 5. Workflow Ownership Summary

字段归属必须遵守下面这条边界：

- `Douyin discovery` 只负责基础发现、标签和趋势判断，不填星图商业字段
- `Xingtu enrichment` 只负责星图商业字段与补齐状态，不重做 Douyin 发现逻辑
- `record_merge_update` 负责把两边产物合并成同一个 `CreatorRecord`

---

## 6. V0 Notes

首版允许保留两种字段形态并存：

- 规范化字段
- 原始页面文本

原因：

- 页面提取逻辑还不稳定
- 真实 selector 尚未沉淀
- V0 更需要“保留上下文”，而不是过早做过深归一化
