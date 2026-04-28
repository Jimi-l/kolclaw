
# 微信建联话术库 - 标签体系 v1.0

&gt; 注意：所有代码层枚举统一使用英文值；中文说明仅用于文档。

---

## 1. 角色（Role）

| 枚举值 | 中文说明 | MVP 映射规则 |
|--------|----------|--------------|
| `agency` | 媒介（我方） | `isSend == 1` |
| `creator` | 达人（对方） | `isSend == 0` |
| `system` | 系统消息 | 异常或缺失发送方向时默认 |

---

## 2. 建联阶段（Stage）

| 枚举值 | 中文说明 | 备注 |
|--------|----------|------|
| `opening` | 开场 | 首次打招呼、破冰 |
| `identity_intro` | 身份介绍 | 自我介绍、公司介绍 |
| `interest_probe` | 兴趣探查 | 询问是否接广、了解合作意向 |
| `price_inquiry` | 价格询问 | 达人询问报价 |
| `price_negotiation` | 价格谈判 | 砍价、议价、预算解释 |
| `brief_alignment` | Brief 对齐 | 发送 brief、确认需求 |
| `schedule_confirmation` | 排期确认 | 确认发布时间、档期 |
| `follow_up` | 跟进 | 催回复、确认进度 |
| `closing` | 收尾 | 确认合作、感谢 |
| `after_sales` | 售后 | 数据反馈、结款、后续合作 |
| `unknown` | 未知 | 无法识别或非建联场景 |

---

## 3. 沟通场景（Scene）

| 枚举值 | 中文说明 | 备注 |
|--------|----------|------|
| `greeting` | 打招呼 | "你好"、"在吗" |
| `self_intro` | 自我介绍 | "我是XX公司的XX" |
| `ask_availability` | 询问是否接广 | "最近有档期吗？"、"接合作吗？" |
| `ask_price` | 询问报价 | "多少钱一条？" |
| `explain_price` | 报价解释 | "我们的报价是..." |
| `bargain` | 砍价 | "能不能便宜点？" |
| `send_brief` | 发 Brief | 发送需求文档、产品信息 |
| `confirm_schedule` | 确认排期 | "XX号可以吗？" |
| `prompt_reply` | 催回复 | "方便回复一下吗？" |
| `handle_objection` | 异议处理 | "价格太高"、"档期不合适" |
| `wrap_up` | 收尾 | "那就这么定了"、"谢谢" |
| `small_talk` | 闲聊/非业务 | 与合作无关的对话 |
| `unknown` | 未知 | 无法识别 |

---

## 4. 意图（Intent）

### 4.1 达人意图（Creator Intent）

| 枚举值 | 中文说明 |
|--------|----------|
| `ask_about_collaboration` | 询问合作 |
| `ask_about_price` | 询问报价 |
| `provide_price` | 提供报价 |
| `decline` | 拒绝 |
| `hesitate` | 犹豫 |
| `request_materials` | 要求资料 |
| `confirm_schedule` | 确认排期 |
| `ask_details` | 追问细节 |
| `small_talk` | 闲聊/非业务 |
| `unknown` | 未知 |

### 4.2 媒介回复意图（Agency Intent）

| 枚举值 | 中文说明 |
|--------|----------|
| `introduce_self` | 自我介绍 |
| `explain_collaboration` | 说明合作 |
| `ask_interest` | 询问意向 |
| `inquire_price` | 询价 |
| `explain_budget` | 解释预算 |
| `negotiate_price` | 议价 |
| `send_brief` | 发送 Brief |
| `confirm_schedule` | 确认排期 |
| `prompt_reply` | 催回复 |
| `address_concern` | 安抚异议 |
| `wrap_up` | 收尾 |
| `small_talk` | 闲聊/非业务 |
| `unknown` | 未知 |

---

## 5. 语气（Tone）

| 枚举值 | 中文说明 |
|--------|----------|
| `polite` | 礼貌 |
| `friendly` | 友好 |
| `professional` | 专业 |
| `urgent` | 紧急 |
| `firm` | 坚定 |
| `soft_push` | 温和催促 |
| `neutral` | 中性 |

---

## 6. 结果（Outcome）

| 枚举值 | 中文说明 | 说明 |
|--------|----------|------|
| `advanced` | 推进 | 对话向前推进了一步 |
| `stalled` | 停滞 | 无进展、对方不回复 |
| `rejected` | 拒绝 | 明确拒绝合作 |
| `waiting` | 等待 | 等待对方回复 |
| `converted` | 转化 | 达成合作 |
| `unknown` | 未知 | 无法判断 |

---

## 7. 标签来源（Label Source）

| 枚举值 | 说明 |
|--------|------|
| `rule_based` | 规则生成（MVP 默认） |
| `llm_annotated` | LLM 标注 |
| `human_reviewed` | 人工审核 |
| `human_override` | 人工覆盖 |

---

## 8. 质量标记（Quality Flags）

用于标记训练样本质量问题：

| Flag | 说明 |
|------|------|
| `non_business` | 非业务对话 |
| `incomplete_context` | 上下文不完整 |
| `contains_sensitive` | 包含敏感信息 |
| `low_relevance` | 低相关性 |
| `needs_human_review` | 需要人工审核 |

