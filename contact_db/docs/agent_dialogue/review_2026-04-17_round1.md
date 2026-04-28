# Round 1 Review - 微信建联话术库 MVP

审查人：Codex  
日期：2026-04-17  
对象：Claude Code 第一版实现

## 总体判断

第一版已经把主链路跑起来了：能读取 WeFlow JSON、输出标准化消息、会话、turn、训练样本、模板候选和运行报告。目录结构和文档方向基本符合项目目标，可以作为 MVP 骨架继续迭代。

但目前有几个会影响“话术库 / 后续大模型数据”的关键问题，需要优先修正。尤其是训练样本切分逻辑和 schema 校验，这两块如果不修，后续真实达人建联数据进来后会产生大量片段化、重复或误标样本。

## 我已做的小修

文件：`src/normalizer.py`

- 修复 `mask_display_name("")` 空字符串崩溃问题。
- 原因：当 `session.displayName` 缺失或为空时，原实现会访问 `name[0]`，导致 `string index out of range`。

## 已验证通过的点

- `python -m compileall -q src scripts` 通过。
- 使用示例文件重新运行 pipeline 成功。
- demo 输出数量符合当前实现：
  - `normalized_messages`: 16
  - `normalized_conversations`: 1
  - `conversation_turns`: 4
  - `training_samples`: 4
  - `template_candidates`: 4
- 非文本图片消息被标记为 `is_text=false`，没有进入训练样本正文。
- URL 在消息内容中会被脱敏为 `[URL]`。

## 高优先级问题

### 1. 训练样本切分没有合并连续同角色消息

设计文档写的是“合并连续同角色消息（默认 5 分钟内）”，但当前 `ConversationTurnBuilder.build_turns()` 实际是逐条 creator 消息找下一条 agency 回复。

这会导致两个问题：

- 连续达人消息只保留最后一条，前面的达人补充信息丢失。
- 如果连续多条达人消息都应共同构成一个问题，训练样本输入会被截断，影响 SFT/RAG 质量。

我用临时合成数据测到：

```text
creator: 你好，我想了解合作
creator: 预算和brief能发我看看吗
agency: 可以的，我这边发你brief和预算范围
```

当前只输出：

```text
预算和brief能发我看看吗 => 可以的，我这边发你brief和预算范围
```

建议改法：

- 先把标准化消息压缩为 `MessageBlock` / `RoleBlock`：
  - 同一 `role`
  - 都是文本
  - 相邻时间差 <= `merge_window_seconds`
  - 合并 `content_masked`，保留原始 `message_ids`
- 再从 block 序列中抽取 `creator_block -> next agency_block`。
- `ConversationTurn` 可以短期继续复用现有 schema，但建议新增字段：
  - `creator_message_ids`
  - `agency_reply_message_ids`
  - `creator_message_text`
  - `agency_reply_text`

如果不想马上改 schema，至少要在构建 TrainingSample 时合并内容，避免丢掉连续消息。

### 2. 目前没有真正的 schema 校验层

README 写了“Schema 校验”，但代码里没有独立 validator，也没有对顶层结构、必填字段和字段类型给出可解释错误。

我用缺失 `session` 的输入测试，当前会继续产出 1 个 conversation，而且没有 warning。修复空 display name 崩溃后，这类坏输入更容易静默进入数据集。

建议新增 `src/validator.py`：

- `validate_weflow_export(raw_data, source_file) -> list[ValidationIssue]`
- 严重错误：
  - 顶层不是 dict
  - 缺少 `session`
  - 缺少 `messages`
  - `messages` 不是 list
  - 消息不是 dict
- 普通 warning：
  - `session.messageCount` 与实际消息数不一致
  - 消息缺少 `formattedTime/source/localType/platformMessageId` 等非阻断字段
  - `isSend` 不在 `{0, 1}`
  - 文本消息 `content` 为空或非字符串
- Pipeline 对严重错误跳过文件，对 warning 写入 report。

### 3. 规则标签在非业务对话上容易误标

示例不是达人建联业务对话，但当前第一条样本被标成：

```text
stage=after_sales
scene=small_talk
```

原因是 `after_sales` 关键词里有“数据”，样例中“数据库”命中了“数据”。这类误标会污染话术库。

建议：

- 先增加 `business_relevance` 或 `is_business_related` 字段。
- 如果命中的关键词只来自泛词，例如“数据”“时间”“可以吗”“好的”，且没有“合作/报价/brief/档期/预算/产品/达人/接广”等强业务词，则优先标记：
  - `stage=unknown`
  - `scene=small_talk` 或 `unknown`
  - `needs_review=true`
- 关键词规则建议分强弱：
  - strong keywords：报价、预算、brief、合作、接广、排期、档期、产品
  - weak keywords：数据、时间、好的、可以、谢谢
- 弱关键词不能单独决定高价值 stage。

### 4. 模板槽位替换顺序有 bug

`template_builder.SLOT_PATTERNS` 里 `[NUMBER]` 规则在 `[AMOUNT]` 之前：

```python
(re.compile(r"\d{1,3}(,\d{3})*(\.\d+)?"), "[NUMBER]")
(re.compile(r"\d+元"), "[AMOUNT]")
```

这会导致 `5000元` 先被替换成 `[NUMBER]元`，后续金额规则无法命中。

建议：

- 把金额、日期、时间、URL 等更具体规则放在数字泛化规则前面。
- 金额规则扩展到：
  - `\d+(\.\d+)?\s*(元|块|万|k|K)`
  - `¥\s*\d+(\.\d+)?`
  - `￥\s*\d+(\.\d+)?`

## 中优先级建议

### 5. `agency` vs `media` 命名需要统一

项目目标里一直说“媒介”，我之前计划里写过 `media`，当前实现使用 `agency`。这不是功能 bug，但要尽早统一，避免后续标注、向量库字段、SFT 数据字段不一致。

建议二选一：

- 保持代码枚举 `agency`，文档中明确 `agency = 媒介 / 我方账号`。
- 或迁移为 `media`，同时兼容旧输出字段。

短期我建议保留 `agency`，但文档和 README 里要写清楚别名关系。

### 6. `quality_flags` 文档和代码没有对齐

taxonomy 文档列了：

- `non_business`
- `incomplete_context`
- `contains_sensitive`
- `low_relevance`
- `needs_human_review`

代码实际主要输出：

- `non_text`
- `empty_content`
- `short_creator_message`
- `short_agency_reply`

建议统一一版 flags，并在代码中补上：

- `non_business_or_unknown_scene`
- `label_unknown`
- `non_text_context`
- `short_input`
- `short_reply`
- `pii_masked`

### 7. Demo 输出文件不建议长期提交为唯一验收依据

当前 demo 使用的样例不是达人建联业务对话，所以它适合验证格式，不适合验证标签质量。后续应新增 2-3 个小型 synthetic fixture：

- 询价场景
- 砍价/预算解释场景
- brief/排期确认场景

这些 fixture 可以放到 `tests/fixtures/` 或 `examples/`，用于回归测试标签和样本构造。

## 建议下一轮修改顺序

1. 新增 `validator.py`，让坏输入可解释地跳过或报警。
2. 重写 turn/sample 构造，先合并连续同角色文本消息，再抽取 `creator -> agency`。
3. 调整业务相关性判断，避免非建联聊天误打高价值标签。
4. 修复模板槽位替换顺序。
5. 补最小测试脚本或 pytest：
   - 示例 JSON 输出行数测试
   - 连续达人消息合并测试
   - 非文本消息不进入训练正文测试
   - 缺失 `session/messages` 的校验测试
   - 金额模板化测试

## 建议验收标准

下一版至少满足：

- 示例 JSON 仍可跑通并输出 7 个文件。
- 连续 creator 消息不会被丢弃。
- 缺失 `session` 或 `messages` 的 JSON 不会静默生成 conversation。
- 非业务样例不应被强行标成 `after_sales`、`price_*`、`brief_alignment` 等高业务阶段。
- `5000元`、`1.5万`、`¥3000` 能模板化为 `[AMOUNT]`。

