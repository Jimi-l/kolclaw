
# 微信建联话术库构建项目 - MVP

**Project Status:** `canonical`

## 项目概述

把大量达人建联会话沉淀成一个可供大模型使用的话术库，支持：
- 从结构化会话中提取"达人消息 → 媒介回复"训练样本
- 对话术按建联阶段、沟通场景、语气、意图进行标签化
- 建立可用于 few-shot / RAG / 后续 SFT 数据准备的话术库

## 快速开始

```bash
cd contact_db
python3 scripts/run_pipeline.py --input-dir . --output-dir ./outputs --prefix demo
```

## 目录结构

```
contact_db/
├── docs/
│   ├── talk_library_design.md      # 系统设计文档
│   └── talk_library_taxonomy.md    # 标签体系文档
├── src/
│   ├── __init__.py
│   ├── schemas.py                   # 数据 schema
│   ├── normalizer.py                # 数据标准化 & 规则标签
│   ├── sample_builder.py            # 训练样本构建
│   ├── template_builder.py          # 话术模板挖掘
│   ├── io_utils.py                  # 读写工具
│   └── pipeline.py                  # Pipeline 主类
├── scripts/
│   └── run_pipeline.py              # CLI 入口
├── outputs/                         # 输出目录
└── 私聊_微梦传媒&像素绽放的Tony华立辉.json  # 示例输入
```

## 核心输出文件

| 文件名 | 说明 |
|--------|------|
| `normalized_messages.jsonl` | 标准化后的单条消息 |
| `conversation_turns.jsonl` | 对话回合（达人→媒介对） |
| `training_samples.jsonl` | 训练样本（含标签和上下文） |
| `template_candidates.jsonl` | 话术模板候选（含评分） |
| `template_candidates.csv` | 模板候选（方便人工查看） |
| `pipeline_report.md` | Pipeline 运行报告 |

## 标签体系

### 角色（Role）
- `agency`: 媒介（我方，isSend=1）
- `creator`: 达人（对方，isSend=0）
- `system`: 系统消息

### 建联阶段（Stage）
`opening` / `identity_intro` / `interest_probe` / `price_inquiry` / `price_negotiation` / `brief_alignment` / `schedule_confirmation` / `follow_up` / `closing` / `after_sales` / `unknown`

### 沟通场景（Scene）
`greeting` / `self_intro` / `ask_availability` / `ask_price` / `explain_price` / `bargain` / `send_brief` / `confirm_schedule` / `prompt_reply` / `handle_objection` / `wrap_up` / `small_talk` / `unknown`

详见 [docs/talk_library_taxonomy.md](docs/talk_library_taxonomy.md)

## 训练样本 Schema

每条训练样本包含：
- `sample_id`, `conversation_id`, `turn_id`
- `stage`, `scene`
- `context_messages`（最近 N 条前文）
- `creator_message`, `agency_reply`
- `creator_intent`, `agency_intent`, `tone`, `outcome`
- `template_candidate`, `quality_score`, `needs_review`, `quality_flags`

## 模板候选评分

- `reusable_score`: 可复用性评分（0.0-1.0）
  - 基于文本长度、槽位数量、使用频次、通用问候语
- `business_value_score`: 业务价值评分（0.0-1.0）
  - 基于建联阶段、沟通场景、关键词

## MVP 实现边界

### 已实现
- 读取多个 WeFlow JSON 文件
- Schema 校验 & 消息标准化
- PII 脱敏（URL、邮箱、手机号、wxid、长数字）
- 角色识别（isSend → agency/creator）
- 训练样本提取（creator→agency 配对）
- 话术模板候选生成（含槽位替换和双评分）
- JSONL/CSV/Markdown 多格式输出

### 规则占位（待优化）
- `stage`/`scene`/`intent`：弱关键词规则 + `unknown`
- `tone`：默认 `neutral`
- `outcome`：默认 `unknown`

### 暂未实现
- LLM 自动标注
- 人工审核队列
- 图片/视频/语音解析
- 数据库存储
- GUI/前端
