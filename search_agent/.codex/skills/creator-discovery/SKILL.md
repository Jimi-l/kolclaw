# Skill: creator-discovery

## 作用

`creator-discovery` 用于在抖音推荐流或候选视频流中，快速识别潜力达人，提取基础数据，判断流量趋势，完成标签分析，并输出标准化 discovery 记录。

它只负责：

- 找达人
- 记基础数据
- 打标签
- 判断是否值得进入下一阶段

它不负责：

- 星图补齐
- 建联
- 报价谈判
- 下单履约
- 返点回收

---

## 何时使用

当任务属于以下任一场景时使用本 skill：

- “开始巡号”
- “刷抖音找潜力达人”
- “识别爆款视频”
- “给达人打标签”
- “录基础表”
- “做一批待补齐达人池”

---

## 进入前必读

执行前按以下顺序读取：

1. `/search_agent/.codex/project.md`
2. `/search_agent/.codex/shared/rules/general.md`
3. `/search_agent/.codex/shared/rules/discovery.md`
4. `/search_agent/.codex/shared/fields/creator_record.md`
5. `/search_agent/.codex/shared/tags/creator_taxonomy.md`
6. 本文件
7. `docs/task.md`
8. `docs/quality_bar.md`
9. `prompts/execution.md`
10. `prompts/labeling.md`

---

## 输入

### 必需输入
- 当前任务描述
- 可访问抖音网页版的浏览器会话

### 可选输入
- 行业/品类偏好
- 目标人群
- 风格偏好
- 预算提示
- 禁投方向
- 地域限制

---

## 输出

输出必须符合：

`/search_agent/.codex/shared/fields/creator_record.md`

至少包含：

- `platform`
- `creator_name`
- `video_url`
- `collection_date`
- `total_interaction_text`
- `follower_count_raw`
- `traffic_trend`
- `persona_tags`
- `content_tags`
- `ad_fit`
- `status`

---

## 核心流程

1. 进入抖音推荐流
2. 快速浏览与跳过
3. 识别潜力视频
4. 记录爆款视频基础数据
5. 进入主页分析达人
6. 判断近期流量趋势
7. 输出标签
8. 形成标准记录
9. 决定：
   - `queue_for_xingtu`
   - `skip`
   - `manual_review`

---

## 成功标准

一条 discovery 结果合格，意味着：

1. 达人身份可识别
2. 视频链接可定位
3. 互动信息可提取
4. 流量趋势判断合理
5. 标签可解释
6. 记录结构稳定
7. 可直接进入后续 xingtu enrichment

---

## 强约束

### 必须做
- 先判断视频是否达标，再进入深度分析
- 进入主页后先暂停视频
- 只取最新 3 条视频做近期判断
- 标签数量受控
- 保留 raw 值
- 记录跳过原因

### 不能做
- 不达标视频强行入表
- 未看清主页就贴标签
- 同一达人重复创建多条相同记录
- 用猜测值替代缺失字段
- 还没确认身份就推进后续补齐

---

## 何时停止

自主模式下满足任一条件即停止：

1. 已连续执行满 20 分钟
2. 已成功形成 10 条合格 discovery 记录

---

## 与下一阶段的交接

满足质量要求的记录：

- `status = queued_for_xingtu`
- `next_action = queue_for_xingtu`

不合格记录：

- `status = skipped` 或 `blocked`

---

## 常见失败模式

- 把直播间当普通视频分析
- 推荐视频进入主页后未暂停，导致最新视频判断错位
- 把“播放中视频后面的 3 条”误认为最新 3 条
- 标签过多、过散
- 同名达人重复入表
- 缺少流量趋势原因说明

遇到上述情况时，优先回退并修正，而不是继续向下游传递脏记录。