
# 微信建联话术库 - 系统设计 v1.0

## 一、项目背景与目标

我们的目标是把大量达人建联会话沉淀成一个可供大模型使用的话术库，最终支持：
1. 从结构化会话中提取"达人消息 → 媒介回复"训练样本；
2. 对话术按建联阶段、沟通场景、语气、意图进行标签化；
3. 建立一个可用于 few-shot / RAG / 后续 SFT 数据准备的话术库；
4. 未来输入"不同建联阶段和场景下的达人消息"，系统可以检索或生成合适的媒介回复。

---

## 二、输入格式分析

### WeFlow JSON 结构

```json
{
  "weflow": { "version", "exportedAt", "generator" },
  "session": { "wxid", "nickname", "remark", "displayName", "type", "lastTimestamp", "messageCount", "avatar" },
  "messages": [
    {
      "localId", "createTime", "formattedTime",
      "type", "localType", "content",
      "isSend", "senderUsername", "senderDisplayName",
      "source", "senderAvatarKey", "platformMessageId"
    }
  ],
  "avatars": { }
}
```

### 原始字段保留策略

| 层级 | 字段 | 保留方式 | 说明 |
|------|------|----------|------|
| 顶层 | `weflow` | 保留元信息 | version、exportedAt、generator |
| 会话 | `wxid` | 哈希化 | SHA1 短哈希作为 contact_id_hash |
| 会话 | `nickname` / `remark` / `displayName` | 脱敏后保留 | contact_display_name_masked |
| 会话 | `type` | 直接保留 | conversation_type |
| 会话 | `lastTimestamp` / `messageCount` | 直接保留 | |
| 消息 | `localId` / `createTime` / `formattedTime` | 直接保留 | |
| 消息 | `type` / `localType` | 直接保留 | |
| 消息 | `content` | 脱敏后保留 | content_masked |
| 消息 | `isSend` | 用于角色推断 | role_inference_source="isSend" |
| 消息 | `senderUsername` | 哈希化 | sender_id_hash |
| 消息 | `senderDisplayName` | 脱敏后保留 | sender_display_name_masked |
| 消息 | `platformMessageId` | 哈希化 | platform_message_id_hash |
| 头像 | `avatars` | 不保留 | 暂不需要 |

---

## 三、四层数据字段设计

### 3.1 会话级（NormalizedConversation）

| 字段 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | string | 会话唯一 ID（SHA1 短哈希） |
| `source_file` | string | 源文件名 |
| `conversation_type` | string | 会话类型（来自 session.type） |
| `contact_display_name_masked` | string | 联系人脱敏后显示名 |
| `contact_id_hash` | string | 联系人 wxid 哈希 |
| `message_count_raw` | int | 原始消息数 |
| `message_count_normalized` | int | 标准化后消息数 |
| `started_at` | int | 会话开始时间戳 |
| `ended_at` | int | 会话结束时间戳 |
| `weflow_version` | string | WeFlow 版本 |
| `exported_at` | int | 导出时间戳 |

### 3.2 消息级（NormalizedMessage）

| 字段 | 类型 | 说明 |
|------|------|------|
| `message_id` | string | 消息唯一 ID |
| `conversation_id` | string | 所属会话 ID |
| `seq_num` | int | 序号 |
| `create_time` | int | 创建时间戳 |
| `formatted_time` | string | 格式化时间 |
| `role` | string | `agency`/`creator`/`system` |
| `role_inference_source` | string | "is_send" 或其他 |
| `role_confidence` | float | 角色置信度（0.0-1.0） |
| `message_type` | string | 消息类型（来自 type） |
| `is_text` | boolean | 是否为纯文本消息 |
| `content_masked` | string | 脱敏后内容 |
| `sender_id_hash` | string | 发送者 ID 哈希 |
| `sender_display_name_masked` | string | 发送者显示名脱敏 |
| `platform_message_id_hash` | string | 平台消息 ID 哈希 |
| `quality_flags` | list[string] | 质量标记 |

### 3.3 业务标签级（ConversationTurn）

| 字段 | 类型 | 说明 |
|------|------|------|
| `turn_id` | string | 对话回合 ID |
| `conversation_id` | string | 所属会话 ID |
| `creator_message` | object | 达人消息（NormalizedMessage） |
| `agency_reply` | object | 媒介回复（NormalizedMessage） |
| `context_messages` | list[object] | 前文消息（最近 N 条） |
| `stage` | string | 建联阶段（枚举） |
| `scene` | string | 沟通场景（枚举） |
| `creator_intent` | string | 达人意图（枚举） |
| `agency_intent` | string | 媒介回复意图（枚举） |
| `tone` | string | 语气（枚举） |
| `outcome` | string | 结果（枚举） |
| `label_source` | string | 标签来源（枚举） |
| `needs_review` | boolean | 是否需要人工审核 |

### 3.4 训练样本级（TrainingSample）

| 字段 | 类型 | 说明 |
|------|------|------|
| `sample_id` | string | 样本唯一 ID |
| `conversation_id` | string | 所属会话 ID |
| `turn_id` | string | 所属对话回合 ID |
| `stage` | string | 建联阶段 |
| `scene` | string | 沟通场景 |
| `context_messages` | list[object] | 上下文消息 |
| `creator_message` | string | 达人消息原文（脱敏） |
| `agency_reply` | string | 媒介回复原文（脱敏） |
| `creator_intent` | string | 达人意图 |
| `agency_intent` | string | 媒介回复意图 |
| `tone` | string | 语气 |
| `outcome` | string | 结果 |
| `template_candidate` | string | 候选话术模板 |
| `quality_score` | float | 质量分数（0.0-1.0） |
| `needs_review` | boolean | 是否需要人工审核 |
| `quality_flags` | list[string] | 质量标记 |

---

## 四、核心分层设计

### Layer 1: 输入校验与标准化
- 读取目录下多个 WeFlow JSON
- Schema 校验（必填字段、类型检查）
- 消息标准化（字段映射、类型统一）
- **规则实现**

### Layer 2: 隐私脱敏
- URL → `[URL]`
- 邮箱 → `[EMAIL]`
- 中国手机号 → `[PHONE]`
- `wxid_...` → `[WECHAT_ID]`
- 长数字串 → `[NUMBER]`
- 连续空白归一化
- **规则实现**

### Layer 3: 规则标签（第一版）
- 角色识别：`isSend=1`→`agency`，`isSend=0`→`creator`
- 建联阶段：关键词弱规则 + `unknown`
- 沟通场景：关键词弱规则 + `unknown`
- 意图：关键词弱规则 + `unknown`
- 语气：默认 `neutral`
- 结果：默认 `unknown`
- **规则实现（可替换为 LLM）**

### Layer 4: 训练样本构造
- 合并连续同角色消息（默认 5 分钟内）
- 提取 `creator → agency` 成对样本
- 保留上下文（最近 N 条消息）
- **规则实现**

### Layer 5: 模板候选沉淀
- 从媒介回复生成模板
- 槽位替换（金额、数字、日期、URL）
- 聚合频次 + 可复用性评分 + 业务价值评分
- **规则实现**

---

## 五、MVP 输出文件

| 文件名 | 格式 | 说明 |
|--------|------|------|
| `normalized_messages.jsonl` | JSONL | 标准化后的单条消息 |
| `conversation_turns.jsonl` | JSONL | 对话回合（达人→媒介对） |
| `training_samples.jsonl` | JSONL | 训练样本（含标签和上下文） |
| `template_candidates.jsonl` | JSONL | 话术模板候选（含评分） |
| `template_candidates.csv` | CSV | 模板候选（方便人工查看） |
| `pipeline_report.md` | Markdown | Pipeline 运行报告 |

---

## 六、规则 vs LLM 标注边界

| 任务 | MVP 实现 | 后续优化 |
|------|----------|----------|
| 角色识别 | 规则（isSend） | 支持人工覆盖 |
| 阶段/场景/意图 | 弱规则 + `unknown` | LLM 标注队列 |
| 语气 | 默认 `neutral` | LLM 标注 |
| 结果 | 默认 `unknown` | LLM + 人工审核 |
| 质量评分 | 启发式规则 | LLM + 人工反馈 |

