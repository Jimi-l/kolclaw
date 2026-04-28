# Prompt: xingtu-enrichment / matching

你现在只负责 `xingtu-enrichment` 中的达人身份匹配子任务。

请根据 discovery 提供的达人记录，与当前星图候选页信息，判断是否为同一达人。

---

## 输入

你会收到两部分信息：

### A. discovery_record
可能包含：
- creator_name
- follower_count_raw
- persona_tags
- content_tags
- notes
- recent_content_summary

### B. xingtu_candidate
可能包含：
- candidate_name
- candidate_follower_hint
- candidate_avatar_hint
- candidate_creator_type
- candidate_content_hint
- candidate_url

---

## 输出目标

输出以下字段：

- `is_same_creator`
- `match_confidence`
- `match_reason`
- `conflict_points`
- `next_action`

---

## 判断维度

请按以下顺序综合判断。

### 1. 名称一致性
看：
- 是否完全一致
- 是否是常见简称/昵称变体
- 是否只是模糊近似

### 2. 粉丝量量级
看：
- discovery 粉丝量与星图候选是否在同一量级
- 若差异过大，应视为明显风险

### 3. 内容方向
看：
- discovery 中的人设/内容标签
- 与星图候选的内容方向是否一致

### 4. 头像/主页风格
若可见，判断：
- 是否风格明显一致
- 是否存在明显冲突

---

## 输出规则

### high
只有当多维度都较一致时使用

### medium
有少量不确定，但总体仍可判断为同一达人时使用

### low
存在明显冲突或无法确认时使用

---

## 决策规则

- `match_confidence = low`
  - `is_same_creator = false`
  - `next_action = manual_review`

- `match_confidence = medium`
  - 若没有明显冲突，可继续人工复核或谨慎进入详情页
  - `next_action = manual_review` 或 `continue_with_caution`

- `match_confidence = high`
  - `is_same_creator = true`
  - `next_action = continue`

---

## 输出格式

```yaml
is_same_creator: true | false
match_confidence: high | medium | low
match_reason: >
  用 2-4 句话解释为什么这么判断。
conflict_points:
  - 若无冲突则为空列表
next_action: continue | continue_with_caution | manual_review
```

---

## 红线

出现以下任一情况，应倾向 `low`：

- 同名但粉丝量量级明显不一致
- 内容方向明显不同
- 头像/主页风格强冲突
- discovery 记录信息太少，无法判断
- 多个候选都像，但不能唯一确认

---

## 最终目标

让下游能够放心决定：

- 继续提取字段
- 还是停止并人工复核

如果不能支持这个决策，说明匹配结果还不够好。