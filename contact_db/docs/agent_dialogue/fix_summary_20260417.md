
# Codex 反馈修复总结 - 2026-04-17

## 修复概述

根据 codex 的 4 点重点反馈，完成了以下修复：

---

## 1. 修复模板槽位替换顺序 bug

**问题**：`[NUMBER]` 规则在 `[AMOUNT]` 前面，导致 "5000元" 被错误模板化为 "[NUMBER]元"

**修复**：[src/template_builder.py](../src/template_builder.py#L19-L30)
- 调整 `SLOT_PATTERNS` 顺序
- `[AMOUNT]` 相关规则（`\d+万`、`\d+元`、`\d+k`、`\d+K`）移到 `[NUMBER]` 前面

---

## 2. 实现独立的 validator.py schema 校验层

**问题**：README 写了 schema 校验，但代码里没有独立 validator

**修复**：新建 [src/validator.py](../src/validator.py)
- `ValidationError` 类：支持 error/warning 两种 severity
- `WeFlowValidator` 类：
  - `validate_file()`: 校验整个文件
  - `_validate_session()`: 校验 session 字段
  - `_validate_message()`: 校验单条消息
- 校验内容：
  - 顶层必须有 `session` 和 `messages`
  - 必填字段检查（`wxid`、`displayName`、`messageCount`、`localId`、`createTime`、`type`、`isSend`、`senderUsername`）
  - `isSend` 必须是 0 或 1
  - `type` 必须是已知消息类型

**集成**：[src/pipeline.py](../src/pipeline.py#L72-L83)
- `_process_files()` 中先做校验，校验失败则跳过该文件并记录警告

---

## 3. 增加业务相关性判断，避免误标非业务聊天

**问题**：示例中"数据库"命中了"数据"关键词，导致被误标为 `after_sales`

**修复**：[src/normalizer.py](../src/normalizer.py#L168-L191)
- 新增 `BUSINESS_RELEVANCE_KEYWORDS`：只有命中这些词才认为是业务聊天
  - 达人、接广、合作、报价、档期、brief、Brief、推广、投放、佣金、坑位费、品牌、产品、结款、数据反馈、视频、图文、直播
- 新增 `is_business_relevant()` 函数
- 修改 `WeakLabeler.label_turn()`：
  - 先判断是否 business relevant
  - 如果不是，直接设为 `stage=unknown`、`scene=small_talk`、`intent=small_talk`
- 优化 `Stage.AFTER_SALES` 关键词：从"数据"改为"数据反馈"、"结款"、"效果数据"、"投放数据"

**效果**：示例中的非业务聊天现在被正确标记为 `small_talk`，不再误标 `after_sales`

---

## 4. 重做训练样本切分，真正合并连续同角色消息

**问题**：之前没有真正合并连续同角色消息，会丢掉连续达人消息里的前置信息

**修复**：重写 [src/sample_builder.py](../src/sample_builder.py)
- 新增 `merge_consecutive_same_role_messages()` 函数：
  - 默认 300 秒（5分钟）内连续同角色消息合并
  - 合并内容用换行符连接
  - 合并质量 flags 去重
  - 取第一条的时间、seq_num、message_id
- 修改 `ConversationTurnBuilder.build_turns()`：
  - 先对原始消息做合并
  - 再在合并后的消息序列中找 `creator → agency` 对

**效果**：
- 之前：4 个训练样本
- 现在：3 个训练样本（连续的 3 条 creator 消息被合并，连续的 4 条 agency 消息被合并）
- 不再丢失前置信息

---

## 验证结果

运行 Pipeline 后的输出变化：

| 指标 | 之前 | 现在 |
|------|------|------|
| 训练样本数 | 4 | 3（正确合并了连续消息） |
| stage 标签 | 有 `after_sales` 误标 | 全部 `unknown`（非业务聊天） |
| scene 标签 | 混杂 | 全部 `small_talk`（正确） |
| intent 标签 | 混杂 | 全部 `small_talk`（正确） |

---

## 修改文件清单

| 文件 | 修改类型 |
|------|----------|
| `src/validator.py` | 新增 |
| `src/normalizer.py` | 修改 |
| `src/sample_builder.py` | 重写 |
| `src/template_builder.py` | 修改 |
| `src/pipeline.py` | 修改 |
| `docs/agent_dialogue/fix_summary_20260417.md` | 新增 |

