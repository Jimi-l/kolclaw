# Workflow

本文档把两份已验证业务提示词，收敛为本地包里的两条粗粒度工作流。

---

## 1. Douyin Discovery Workflow

业务来源：

- `AI智能巡号_抖音版_执行提示词_V3.md`

### Business Goal

在抖音推荐流中持续浏览内容，快速跳过无价值视频，识别潜力爆款，分析达人画像并生成基础达人记录。

### Preserved Business Sequence

1. 登录抖音网页版
2. 进入推荐流并确认推荐内容正常加载
3. 快速刷视频，模拟真人浏览节奏
4. 先过滤广告 / 直播 / 低信号视频
5. 对潜力视频做基础字段提取
6. 进入达人缩略主页做账号级分析
7. 判断流量趋势
8. 生成人设 / 内容 / 场景 / 广告类型标签
9. 写入基础 creator record
10. 达到终止条件后输出 summary

### Candidate Detection Rules

满足任一条件即可视为潜力视频：

- 点赞数 `>= 20万`
- 转发数 `>= 10万`
- 收藏数 `>= 10万`
- 评论数 `>= 1万`

应优先快速跳过：

- 广告视频
- 直播视频
- 明显低于阈值的视频

### Base Fields Collected In Discovery

- `capture_date`
- `video_url`
- `publish_date` / `publish_time_text`
- `freshness_score`
- `like_count`
- `comment_count`
- `share_count`
- `favorite_count`
- `total_interaction_text`
- `creator_name`
- `follower_count`
- `ai_generated_flag`

### Profile Analysis Preserved From The Spec

达人主页分析必须保留下面这些业务动作，即使当前实现仍是 skeleton：

1. 确认达人名称 / 粉丝量 / 获赞
2. 判断推荐视频位于置顶还是中间
3. 取近 3 条最新视频点赞数
4. 计算近 3 条平均点赞
5. 对比推荐视频点赞，给出流量趋势
6. 生成人设标签
7. 生成内容标签
8. 生成内容关键场景
9. 给出广告类型适配

### Traffic Trend Rules

- `近3条平均点赞 < 推荐视频点赞 * 1/5` -> `昙花一现`
- `近3条平均点赞 < 推荐视频点赞 * 1/2` -> `流量波动`
- `近3条平均点赞 >= 推荐视频点赞 * 1/2` -> `持续爆款`

### Stop Conditions

二选一，先到为准：

- 连续执行满 `20 分钟`
- 成功写入 `10 个`潜力账号

### Exception Strategy

首版包保留异常处理接口，但不做生产级兜底：

- 登录失效 -> 记录并终止当前 run
- 人机验证 -> 记录并标记人工介入
- 字段抓取失败 -> 保留部分结果和失败说明
- 网络异常 -> 重试 / 跳过 / 记录
- 重复达人 -> 走 merge/update，而不是重复创建

### Current Implementation Boundary

`tools/douyin_workflow.py` 当前提供的是：

- orchestration skeleton
- mock feed
- threshold/filter rules
- workflow logging
- local persistence
- TODO 标记位

当前没有做：

- 稳定页面 selector
- 真实 F 键进主页策略
- 真实 HTML 提取 `aweme_id`
- 真实推荐流滑动和播放控制

---

## 2. Xingtu Enrichment Workflow

业务来源：

- `AI智能巡号_星图数据补充_执行提示词.md`

### Business Goal

基于已有达人记录，筛出星图字段为空的达人，进入星图平台搜索匹配后提取商业化数据并回填。

### Preserved Business Sequence

1. 登录星图平台
2. 获取待补齐达人列表
3. 逐个搜索达人
4. 核对达人匹配
5. 进入详情页提取星图字段
6. 保存近 15 条播放曲线截图
7. 回填记录
8. 标记 enrichment status
9. 输出 run summary

### Required Enrichment Fields

- `xingtu_id`
- `creator_types`
- `xingtu_profile_url`
- `price_20s`
- `price_20_to_60s`
- `price_60s_plus`
- `estimated_play_volume`
- `sponsored_play_median`
- `organic_cpm`
- `cpe`
- `completion_rate`
- `play_curve_screenshot`
- `monthly_follower_growth_rate`
- `connected_user_fan_ratio`
- `deep_user_fan_ratio`
- `cooperative_clients`

### Matching Logic

在骨架层面保留以下匹配原则：

- 先按达人名称搜索
- 以粉丝量、头像、主页信息辅助校验
- 若找不到，则记录 `not_found`
- 若未入驻，则记录 `not_registered`
- 若字段不完整，则允许 `partial`

### Source Of Pending Records In V0

验证过的业务流程里，待补齐列表来自飞书多维表格。

但在本地骨架版里，为了先保证可运行和可迭代，默认待补齐列表来源为本地 SQLite：

- `storage.get_creators_missing_xingtu()`

`feishu_client.py` 已预留 stub，用于下一阶段接回真实飞书。

### Current Implementation Boundary

`tools/xingtu_workflow.py` 当前提供的是：

- pending record fetch
- mock search / enrich path
- enrichment state update
- logging and checkpoint hooks

当前没有做：

- 真实星图 selector
- 真实登录态维护
- 真实截图采集
- 真实飞书表格写回

---

## 3. Shared Runtime Contract

两个 workflow 共享同一组基础设施：

- `browser_runtime.py`
- `llm_client.py`
- `feishu_client.py`
- `storage.py`
- `models.py`
- `utils.py`

共享原则：

- workflow 保持粗粒度，不拆很多小模块
- 真正不稳定的页面交互收敛到 runtime / workflow TODO 中
- 业务字段通过模型统一
- 所有 run 都有 summary、日志、checkpoint

---

## 4. Practical V0 Intention

这版最重要的产物不是“真实跑满全流程”，而是：

- 让业务逻辑有地方落
- 让字段边界先清楚
- 让下一轮迭代知道应该替换哪些空心点

换句话说，这个包已经具备“可继续长”的主干，但还没有故作完整。
