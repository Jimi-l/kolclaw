# Skill: xingtu-enrichment

## 作用

`xingtu-enrichment` 用于消费 discovery 阶段已经筛出的达人记录，在星图中完成身份确认与商业字段补齐。

它只负责：

- 搜索达人
- 判断是否为同一达人
- 提取星图字段
- 标记补齐状态
- 产出结构化 enrichment 结果

它不负责：

- 抖音巡号
- 基础标签分析
- 建联
- 谈价
- 下单履约
- 返点回收

---

## 何时使用

当任务属于以下任一场景时使用本 skill：

- “补齐星图数据”
- “查这批达人星图价格”
- “把星图字段补完整”
- “给 discovery 结果做二筛商业数据”
- “只处理星图 id 为空的记录”

---

## 进入前必读

执行前按以下顺序读取：

1. `/search_agent/.codex/project.md`
2. `/search_agent/.codex/shared/rules/general.md`
3. `/search_agent/.codex/shared/rules/xingtu.md`
4. `/search_agent/.codex/shared/fields/xingtu_record.md`
5. 本文件
6. `docs/task.md`
7. `docs/quality_bar.md`
8. `prompts/execution.md`
9. `prompts/matching.md`

---

## 输入

### 必需输入
- 已完成 discovery 的达人记录
- 可访问星图的浏览器会话

### 最小输入字段
- `creator_name`
- `follower_count_raw`
- `persona_tags`
- `content_tags`
- `status`

### 可选输入
- 头像线索
- 达人主页简介摘要
- discovery notes
- 近 3 条内容方向摘要

---

## 输出

输出必须符合：

`/search_agent/.codex/shared/fields/xingtu_record.md`

至少包含：

- `xingtu_id`
- `xingtu_profile_url`
- `xingtu_creator_type`
- `match_confidence`
- `match_reason`
- `search_name_used`
- `enrichment_status`
- `next_action`

如果字段可见，还应补齐：

- `price_20s`
- `price_20_60s`
- `price_60s_plus`
- `estimated_play`
- `sponsored_median_play`
- `natural_cpm`
- `cpe`
- `sponsored_completion_rate`
- `monthly_fan_growth_rate`
- `monthly_connected_user_fan_ratio`
- `monthly_deep_user_fan_ratio`
- `cooperate_brands`
- `recent_15_curve_screenshot_path`

---

## 核心流程

1. 读取待补齐记录
2. 在星图搜索达人
3. 通过粉丝量、头像、内容方向判断是否同一达人
4. 若匹配成功，进入详情页
5. 提取商业字段
6. 保存截图路径
7. 输出 enrichment 结果
8. 标记：
   - `xingtu_completed`
   - `field_partial`
   - `xingtu_not_found`
   - `xingtu_unregistered`
   - `ambiguous_match`
   - `blocked`

---

## 成功标准

一条 enrichment 结果合格，意味着：

1. 搜索过程可复核
2. 匹配逻辑可解释
3. 关键字段来自同一达人详情页
4. 缺失字段被明确记录
5. 状态可供后续流程直接消费

---

## 强约束

### 必须做
- 先做身份匹配，再做字段回填
- 不确认同一达人，不回填价格
- 记录匹配理由
- 记录缺失字段
- 保留状态

### 不能做
- 同名达人未确认就回填
- 价格来自 A，其他字段来自 B
- 搜不到就随便用近似达人替代
- 看不到字段就脑补
- 把 discovery 阶段的推测当作星图事实

---

## 何时停止

单轮处理完成以下任一情况可结束：

1. 当前待补齐队列处理完
2. 登录失效或权限阻塞
3. 连续出现系统性异常，需要人工检查

---

## 与上一阶段的接口

本 skill 只消费以下状态的记录：

- `queued_for_xingtu`

默认不消费：

- `skipped`
- `blocked`
- `xingtu_completed`

---

## 常见失败模式

- 同名达人多，直接选第一个
- 粉丝量量级明显对不上仍继续回填
- 只看昵称，不看内容方向
- 字段缺失但未写入 `field_missing_list`
- 页面权限不足还强行输出完整结果

遇到上述情况时，优先降级为：
- `ambiguous_match`
- `field_partial`
- `blocked`

而不是伪造完整结果。


