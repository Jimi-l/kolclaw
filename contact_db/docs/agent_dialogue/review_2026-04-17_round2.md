# Round 2 Review - 修复版审查

审查人：Codex  
日期：2026-04-17  
对象：Claude Code 对 Round 1 反馈的修复版

## 总体判断

这轮修复方向是对的，MVP 已经比第一版更接近“可沉淀话术库”的数据形态：

- validator 已接入 pipeline，严重坏输入会跳过。
- 连续同角色消息已经会合并，示例训练样本从 4 条变成 3 条。
- 示例非业务聊天不再被误标为 `after_sales`。
- 模板槽位替换顺序已调整。

我又补了一个小修：扩展金额模板化规则，使 `5000元`、`1.5万`、`¥3000`、`2k`、`3 K` 都能归一为 `[AMOUNT]`。修改文件：`src/template_builder.py`。

## 我验证过的结果

命令验证：

- `python -m compileall -q src scripts` 通过。
- 示例文件重新跑 pipeline 成功。
- 当前输出数量：
  - `normalized_messages`: 16
  - `normalized_conversations`: 1
  - `conversation_turns`: 3
  - `training_samples`: 3
  - `template_candidates`: 3

示例训练样本现在是：

```text
1. stage=unknown, scene=small_talk
2. stage=unknown, scene=small_talk
3. stage=unknown, scene=small_talk
```

这符合当前样例“不是典型达人建联业务对话”的事实。

validator 测试：

- 缺失 `session`：跳过文件，并写 warning。
- `messages` 不是 list：跳过文件，并写 warning。

连续消息合并测试：

```text
creator: 你好，我想了解合作
creator: 预算和brief能发我看看吗
agency: 可以的，我这边发你brief和预算范围
```

当前输出 1 条样本：

```text
你好，我想了解合作
预算和brief能发我看看吗
=>
可以的，我这边发你brief和预算范围
```

说明连续 creator 消息已经不会丢失。

金额模板化测试：

```text
报价5000元，可以优惠到1.5万 => 报价[AMOUNT]，可以优惠到[AMOUNT]
预算是¥3000，另有2k服务费 => 预算是[AMOUNT]，另有[AMOUNT]服务费
价格 3 K 可以吗 => 价格 [AMOUNT] 可以吗
报价￥ 2999.5 => 报价[AMOUNT]
```

## 仍需修的高优先级问题

### 1. 合并后的消息缺少可追溯性

当前合并消息复用了第一条消息的：

- `message_id`
- `seq_num`
- `formatted_time`
- `platform_message_id_hash`

但被合并的其他原始消息 id 没有保留下来。后续人工审核、回溯原聊天、定位问题样本时会丢信息。

建议下一版补 schema：

- 在 `ConversationTurn` 或新增 `MessageBlock` 中加入：
  - `creator_message_ids`
  - `agency_reply_message_ids`
  - `creator_seq_nums`
  - `agency_seq_nums`
  - `start_time`
  - `end_time`
- `TrainingSample` 也保留：
  - `source_message_ids`
  - `source_seq_nums`

短期可不大改 dataclass，但至少在 turn/sample 输出中补这些字段。

### 2. 业务相关性判断容易误伤和误放

这轮加了 `BUSINESS_RELEVANCE_KEYWORDS`，是必要的。但现在词表中有一些泛词：

- `视频`
- `图文`
- `品牌`
- `产品`

这些词在普通聊天中也很常见，可能把非业务聊天误判成业务。反过来，真实建联里可能出现“商单”“报价单”“小红书”“抖音”“星图”“蒲公英”“植入”“寄样”等词，目前没有覆盖。

建议把业务相关性分成两层：

- strong business keywords：`接广`、`商单`、`报价`、`预算`、`brief`、`排期`、`档期`、`坑位费`、`佣金`、`寄样`、`星图`、`蒲公英`、`合作`
- weak business keywords：`视频`、`图文`、`品牌`、`产品`、`数据`

规则：

- strong 命中即可视为业务相关。
- weak 需要至少两个弱词同时命中，或与金额/排期/平台词共同出现。
- 非业务但提到“视频/产品”的聊天不要直接进入高价值 stage。

### 3. stage/scene 规则的优先级需要调整

当前 `weak_label_stage()` 按 `KEYWORDS_STAGE` 顺序返回第一个命中。这个会导致带问候语的真实业务消息被低价值标签覆盖。

我测的样本：

```text
你好，我想了解合作
预算和brief能发我看看吗
```

当前被标为：

```text
stage=opening
scene=greeting
```

但更有价值的标签应该接近：

```text
stage=brief_alignment 或 price_negotiation/price_inquiry
scene=send_brief 或 ask_price
```

建议：

- 不要按字典顺序返回第一个命中。
- 给 stage/scene 加权：
  - brief / 报价 / 预算 / 排期 / 档期 权重大于 你好 / 嗯嗯 / 好的。
  - 多个标签命中时选最高权重。
- 或先识别高价值业务场景，再识别 opening/closing。

### 4. `needs_review` 对 small_talk 过于宽松

当前逻辑：

```python
if turn.stage == Stage.UNKNOWN and turn.scene != Scene.SMALL_TALK:
    turn.needs_review = True
```

这意味着所有 `small_talk` 都不需要 review。但从话术库角度，非业务聊天通常不应该直接进入高质量训练集，至少应进入低优先级或 review 队列。

建议：

- `small_talk` 样本设置：
  - `needs_review=true`
  - `quality_flags` 加 `non_business`
  - `quality_score` 降低
- 或增加输出文件：
  - `*_training_samples.jsonl`
  - `*_review_samples.jsonl`
  - `*_excluded_samples.jsonl`

MVP 可以先不排除，但要能区分“可训练样本”和“格式正确但业务价值低的样本”。

## 中优先级建议

### 5. validator 可以更可解释

现在 `filename` 参数没有使用；`session.messageCount` 和实际消息数不一致也没有 warning。

建议补：

- `session.messageCount != len(messages)` 作为 warning。
- 文本消息 `content is None` 作为 warning。
- 非文本消息 `content is None` 不作为异常，只作为正常标记。

### 6. 文档链接相对路径有小问题

`docs/agent_dialogue/fix_summary_20260417.md` 中的链接写成：

```md
[src/template_builder.py](../src/template_builder.py)
```

从 `docs/agent_dialogue/` 出发，正确路径应是：

```md
[src/template_builder.py](../../src/template_builder.py)
```

不影响代码，但建议下次顺手改掉。

### 7. 需要补最小自动化测试

现在主要靠手工运行。下一轮建议加入最小 pytest 或脚本化测试，覆盖：

- 示例 JSON 跑通并输出 7 个文件。
- 缺失 `session` 会跳过。
- 连续 creator 消息合并为一个样本。
- `small_talk` 不进入高价值标签。
- 金额模板化覆盖 `5000元`、`1.5万`、`¥3000`、`2k`。

## 建议下一轮修改顺序

1. 补合并后样本的可追溯字段：原始 message ids、seq nums、start/end time。
2. 调整业务相关性：strong/weak keyword 分层，避免 `视频/图文/产品` 单独触发业务标签。
3. 调整 stage/scene 优先级：高价值业务标签优先于 greeting/opening。
4. 让 `small_talk` 样本带 `non_business` quality flag，并默认 `needs_review=true` 或进入单独输出。
5. 补最小测试，防止后续改规则时反复回退。

## 下一步产品方向建议

代码层面稳定后，不要急着接向量库或 SFT。下一步最有价值的是引入 10-20 个真实达人建联 JSON，做一轮“标签口径校准”：

- 哪些样本应进入主训练集？
- 哪些只适合做检索参考？
- 哪些应该排除？
- `stage/scene/intent` 是否够用？
- 业务方是否接受 `agency` 这个字段名？

这一步决定话术库的数据质量上限。

