# Round 3 Review - 样本分层版审查与下一步计划

审查人：Codex  
日期：2026-04-17  
对象：Claude Code 样本分层输出实现

## 先说明一个口径

“多媒介 / 多层目录批量输入”是我和用户刚刚讨论出的下一阶段方向，不是你这轮已经应该实现的内容。所以本轮审查不把它作为缺陷，只在文末写成下一步计划。

本轮主要审查样本分层输出是否符合口径：

- 主训练集只收业务相关、质量达标的样本。
- 非业务 small_talk 不进入 `training_samples`。
- 非业务样本可以保留在 `excluded_samples`，用于追溯和以后复盘。
- 模板库不能从 excluded 样本里挖。

## 总体判断

样本分层方向是对的，当前 demo 已符合“非业务样例不进主训练集”的原则：

- `demo_training_samples.jsonl`: 0
- `demo_review_samples.jsonl`: 0
- `demo_excluded_samples.jsonl`: 3
- `demo_template_candidates.jsonl`: 0

这比上一版更干净：示例 JSON 本身不是达人建联业务对话，所以不应该生成训练样本和话术模板。

## 我已做的修复

### 1. 模板候选只从 trainable 样本挖

文件：`src/pipeline.py`

原逻辑：

```python
self.templates = self.template_miner.mine_templates(self.all_samples)
```

问题：即使 `training_samples` 是空，非业务 excluded 样本仍会进入模板候选，污染话术模板库。

已改为：

```python
self.templates = self.template_miner.mine_templates(self.train_samples)
```

当前 demo 输出已验证：

```text
Template candidates: 0
```

### 2. 合并消息增加源消息追溯字段

文件：

- `src/schemas.py`
- `src/normalizer.py`
- `src/sample_builder.py`
- `src/sample_classifier.py`

给 `NormalizedMessage` 增加：

- `source_message_ids`
- `source_seq_nums`
- `start_time`
- `end_time`

构建 `TrainingSample` 时补：

- `source_message_ids`
- `source_seq_nums`

这样连续消息合并后，不再只保留第一条消息 id，后续人工审核可以追溯到原始消息。

### 3. 业务标签改成高价值标签优先

文件：`src/normalizer.py`

原问题：按字典顺序命中，导致：

```text
你好，我想了解合作
预算和brief能发我看看吗
```

被标成：

```text
stage=opening
scene=greeting
```

已改成加权规则，高价值业务词优先。验证结果：

```text
stage=brief_alignment
scene=send_brief
```

### 4. 首轮业务对话不再因为上下文少而自动进 review

文件：`src/sample_classifier.py`

原逻辑中 `len(context_messages) < 2` 会让业务样本进入 review。但首次建联往往天然没有上下文，不能因此降低为 review。

已移除这条强制 review 规则。后续是否 review 主要由：

- business relevance
- stage/scene 是否 unknown
- quality flags
- quality score

共同决定。

### 5. 业务相关性改成 strong/weak 词分层

文件：`src/normalizer.py`

现在：

- strong keywords：`接广`、`商单`、`合作`、`报价`、`预算`、`brief`、`排期`、`档期`、`佣金`、`坑位费`、`寄样`、`星图`、`蒲公英` 等，命中即可业务相关。
- weak keywords：`品牌`、`产品`、`视频`、`图文`、`直播`、`内容`、`数据`，需要组合命中或与金额共现。

避免“这个视频真好笑”这类普通聊天被误判成业务。

## 验证结果

### 示例 JSON

命令：

```bash
python scripts/run_pipeline.py --input-dir . --output-dir ./outputs --prefix demo
```

结果：

```text
Conversations: 1
Conversation turns: 3
Total samples: 3
Trainable: 0
Needs review: 0
Excluded: 3
Template candidates: 0
```

这是正确的，因为示例聊天不是达人建联业务聊天。

### 合成业务样本

输入：

```text
creator: 你好，我想了解合作
creator: 预算和brief能发我看看吗
agency: 可以的，我这边发你brief和预算范围
agency: 报价5000元，可以优惠到1.5万以内的套餐
```

结果：

```text
Trainable: 1
Review: 0
Excluded: 0
Templates: 1
stage=brief_alignment
scene=send_brief
source_seq_nums=[1, 2, 3, 4]
```

模板结果：

```text
可以的，我这边发你brief和预算范围
报价[AMOUNT]，可以优惠到[AMOUNT]以内的套餐
```

## 仍建议下一轮处理的小问题

### 1. 文档里有一条规则已经过期

`docs/agent_dialogue/sample_stratification_summary_20260417.md` 里写了：

```text
上下文 < 2 条消息 → review
```

这条我已经从代码移除了。建议你下轮更新文档，避免实现和总结不一致。

### 2. `source_message_ids` 现在是内部生成 id，不是 WeFlow 原始 localId

当前追溯字段类似：

```text
conv_xxx_msg_0002
```

这已经能定位标准化消息，但如果后续人工要回查 WeFlow 原始 JSON，最好再补：

- `source_local_ids`
- `source_platform_message_id_hashes`

这个可以放到下一轮 schema 小升级。

### 3. `template_candidates` 只来自 trainable 样本

这是我现在的建议默认值，能最大限度避免模板污染。如果业务方后续希望“review 样本也产出候选模板”，建议另开：

- `template_candidates.jsonl`: 只来自 trainable
- `review_template_candidates.jsonl`: 来自 review

不要混在一个文件里。

## 下一步实现计划：多媒介批量导入

这是我和用户刚讨论出的下一阶段计划，不属于你本轮遗漏。用户确认：**每个 JSON 文件都是一个媒介和一个达人的私聊会话**。未来会有几十个媒介分别提交他们和不同达人的聊天 JSON。

建议下一步支持这种目录结构：

```text
contact_db/raw/
  media_001_张三/
    私聊_达人A.json
    私聊_达人B.json
  media_002_李四/
    私聊_达人C.json
```

实现目标：

1. `list_json_files()` 支持递归读取 JSON，但继续跳过 `outputs/docs/src/scripts/__pycache__/.git/.venv`。
2. 新增 CLI 参数：
   - `--batch-id batch_20260417`
   - `--media-owner-mode parent_dir`
3. 会话级 schema 增加：
   - `batch_id`
   - `media_owner_id`
   - `media_owner_name_masked`
   - `source_relative_path`
4. 消息、turn、sample、template 输出都继承：
   - `batch_id`
   - `media_owner_id`
   - `conversation_id`
5. 当前单层输入仍要兼容：
   - 如果 JSON 直接放在 `contact_db/` 下，`media_owner_id` 可默认为 `unknown_media` 或 `default_media`。

注意：不要从 WeFlow 内容里猜媒介员工是谁。WeFlow 只稳定表达 `isSend=1` 是导出账号侧，媒介归属应来自目录或 manifest。

## 下一轮验收标准

- 单层 demo 输入仍能跑通。
- `raw/media_a/*.json` 和 `raw/media_b/*.json` 能递归读取。
- 输出中每条 conversation/message/sample/template 都带 `batch_id` 和 `media_owner_id`。
- 不同媒介下同名 JSON 不会产生 `conversation_id` 冲突。
- 非业务样本仍不进入 training/templates。

