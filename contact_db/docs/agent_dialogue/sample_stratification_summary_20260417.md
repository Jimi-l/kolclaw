
# 样本分层输出实现总结 - 2026-04-17

## 实现概述

按照要求，实现了样本分层输出，主训练集只收业务相关对话，非业务对话进入 excluded_samples，保留可追溯性。

---

## 修改内容

### 1. 更新 schemas.py - 增加样本筛选字段

新增枚举：
- `BusinessRelevance`: `business` / `non_business` / `uncertain`
- `SampleStatus`: `trainable` / `needs_review` / `excluded`
- `ExclusionReason`:
  - `non_business_small_talk`
  - `no_valid_reply`
  - `only_link`
  - `only_emoji`
  - `non_text_only`
  - `short_content`
  - `low_quality`
  - `other`

`TrainingSample` 新增字段：
- `business_relevance: BusinessRelevance`
- `sample_status: SampleStatus`
- `exclusion_reason: Optional[ExclusionReason]`
- `source_message_ids: List[str]`
- `source_seq_nums: List[int]`

---

### 2. 新增 sample_classifier.py - 样本分类器

`SampleClassifier` 类实现：

- `classify_samples()`: 返回 (train_samples, review_samples, excluded_samples)
- `_classify_single_sample()`: 单样本分类逻辑
- `_check_exclusion()`: 检查是否需要排除
  - 非业务 small_talk → 排除
  - 内容过短（&lt; 5 字符）→ 排除
  - 纯链接 → 排除
  - 纯表情 → 排除
  - 非文本消息 → 排除
- `_should_go_to_review()`: 检查是否需要人工审核
  - 业务相关但 stage/scene 为 unknown → review
  - 上下文 &lt; 2 条消息 → review
  - 有 quality_flags → review

---

### 3. 更新 io_utils.py - 支持分层输出

- `write_report()` 函数签名更新，支持传入 train/review/excluded 三类样本
- Report 中新增：
  - Exclusion Reasons 统计
  - 分层样本计数（Trainable / Needs review / Excluded）

---

### 4. 更新 pipeline.py - 实现分流逻辑

- 导入 `SampleClassifier`
- 新增成员变量：
  - `all_samples`
  - `train_samples`
  - `review_samples`
  - `excluded_samples`
- `_classify_samples()` 步骤：在 `_build_samples()` 之后、`_mine_templates()` 之前
- `_write_outputs()` 输出三个样本文件：
  - `*_training_samples.jsonl`
  - `*_review_samples.jsonl`
  - `*_excluded_samples.jsonl`
- `_write_report()` 使用新签名

---

### 5. 更新 scripts/run_pipeline.py - 更新打印逻辑

打印内容更新：
- 总样本数
- Trainable / Needs review / Excluded 分类计数

---

## 验证结果

运行示例 JSON 后的输出：

| 指标 | 数值 |
|------|------|
| 总样本数 | 3 |
| Trainable | **0** ✅ |
| Needs review | 0 |
| Excluded | 3 |
| Exclusion Reason | `non_business_small_talk`: 3 |

符合预期：示例不是建联业务对话，所有样本都进入 `excluded_samples`，`training_samples` 为空。

---

## 输出文件清单

新增输出：
- `demo_training_samples.jsonl` - 高质量业务样本（当前为空）
- `demo_review_samples.jsonl` - 需要人工审核的样本（当前为空）
- `demo_excluded_samples.jsonl` - 被排除的样本（3 条，含 `exclusion_reason`）

保留输出：
- `demo_normalized_conversations.jsonl`
- `demo_normalized_messages.jsonl`
- `demo_conversation_turns.jsonl`
- `demo_template_candidates.jsonl`
- `demo_template_candidates.csv`
- `demo_pipeline_report.md`

---

## 修改文件清单

| 文件 | 修改类型 |
|------|----------|
| `src/schemas.py` | 修改（新增枚举和字段） |
| `src/sample_classifier.py` | 新增 |
| `src/io_utils.py` | 修改（report 支持分层统计） |
| `src/pipeline.py` | 修改（集成分类器，分流输出） |
| `src/__init__.py` | 修改（导出新枚举） |
| `scripts/run_pipeline.py` | 修改（打印逻辑更新） |
| `docs/agent_dialogue/sample_stratification_summary_20260417.md` | 新增 |

