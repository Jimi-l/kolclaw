# External Knowledge Review - KolClaw 经验话术表

审查人：Codex  
日期：2026-04-17  
文件：`external_data/KolClaw达人标签&沟通话术.xlsx`

## 总体判断

这份 Excel 很有价值，不应该只当成“几条固定话术模板”导入。它更像一份人工整理的媒介经验知识库，里面同时包含：

- 达人账号画像标签
- 行业 / 内容分类标签
- 建联 workflow
- 添加新达人场景话术
- 商务询价话术
- brief 框架
- 砍价话术
- 平台标签映射

它可以帮助我们把系统从“只从聊天记录里抽样本”升级成：

```text
历史聊天样本库 + 媒介专家知识库 + 场景模板库 + 标签标准库
```

也就是说，WeFlow JSON 是真实对话数据；这份 Excel 是专家经验和标准口径。两者应该互相补充，而不是互相替代。

## Excel 结构摘要

我解析到 12 个工作表：

1. `账号标签类型`
   - 账号基础信息、画像、内容能力、商业合作能力等字段定义。
   - 可作为 creator profile schema 的来源。

2. `New行业分级标签`
   - 一级 / 二级 / 三级 / 四级行业标签。
   - 行数很多，适合做行业 taxonomy。

3. `职业、兴趣、生活、出镜标签`
   - 职业标签、兴趣标签、生活阶段、出镜关系。
   - 可作为达人画像标签。

4. `添加新好友常规workflow`
   - 添加微信、初次自我介绍、切到企微、正式询价的步骤。
   - 可映射到 `opening`、`identity_intro`、`interest_probe`。

5. `添加新达人知识库`
   - 按平台、账号状态、建联方式给出信息填写要求和话术举例。
   - 覆盖抖音星图、小红书蒲公英、私信、主页联系方式等。

6. `商务沟通知识库-询价及沟通话术`
   - 原创视频、原创图文、线下活动、直播、权益等询价模板。
   - 这是非常重要的 `price_inquiry` / `brief_alignment` 模板种子。

7. `达人brief框架拆解`
   - 产品信息、传播诉求、合作信息、执行要求等 brief 字段。
   - 可用于后续生成 structured brief schema。

8. `砍价话术场景`
   - 达人返点达标 / 不达标、争取返点、复投理由、客户资源背书等。
   - 可作为 `price_negotiation` 模板种子。

9. `补充`
   - 星图 / 蒲公英相关达人标签和人设信息。

10. `工作表2`
    - 更细的人设 / 家庭身份 / 出镜关系标签。

11. `工作表1`
    - 多平台行业标签和账号标签映射。

12. `工作表4`
    - 内容分类标签。

## 应该怎么利用这份文件

### 1. 作为“外部专家模板库”，不要混进聊天训练样本

这份 Excel 不是达人真实回复链路，不应该直接生成：

```text
creator_message -> agency_reply
```

它应该单独产出：

```text
external_templates.jsonl
external_taxonomy.jsonl
external_workflows.jsonl
external_brief_schema.json
```

然后在 RAG / few-shot / LLM 标注时作为辅助知识。

建议新增一个独立模块：

```text
src/external_knowledge.py
```

负责读取 `external_data/*.xlsx`，输出结构化外部知识。

### 2. 作为话术模板候选的“种子模板”

当前模板候选只来自 trainable 样本，这是对的，因为可以避免非业务聊天污染模板库。

但这份 Excel 里的专业话术可以进入另一类模板：

```text
template_source = expert_seed
```

和聊天中挖出来的模板区分：

```text
template_source = conversation_mined
```

建议 `TalkTemplate` 后续增加：

- `template_source`: `conversation_mined` / `expert_seed`
- `source_file`
- `source_sheet`
- `source_row`
- `platform`
- `scenario`
- `stage`
- `scene`
- `slots`

不要把 expert seed 和真实聊天挖出的模板直接混成一个来源，否则后续很难评估哪个模板真的被媒介使用过。

### 3. 反哺 stage / scene / intent 标签体系

Excel 中的工作表可以直接映射到我们的标签体系：

| Excel 工作表 | 建议映射 |
|---|---|
| 添加新好友常规workflow | `opening` / `identity_intro` / `interest_probe` |
| 添加新达人知识库 | `opening` / `identity_intro` / `interest_probe` |
| 商务沟通知识库-询价及沟通话术 | `price_inquiry` / `brief_alignment` / `schedule_confirmation` |
| 达人brief框架拆解 | `brief_alignment` |
| 砍价话术场景 | `price_negotiation` |

这能让我们的弱规则更贴近真实业务，而不是只靠几个手写关键词。

### 4. 反哺 business relevance 词表

从 Excel 里可以抽出更完整的业务词：

- 平台：星图、蒲公英、抖音、小红书、B站、快手、聚光、微任务
- 合作形式：原创视频、原创图文、直播、线下活动、寄拍、送拍
- 商务要素：返点、裸价、改价下单、含税专票、票面点、差旅、授权、投流、排竞、保量
- brief 要素：品牌名称、产品名称、传播周期、营销目的、发布时间、合作平台、合作形式

建议把这些进入：

```text
STRONG_BUSINESS_KEYWORDS
```

或者更好地拆成：

```text
business_terms.json
  platforms
  collaboration_forms
  pricing_terms
  brief_terms
  negotiation_terms
```

这样规则不散落在代码里，后续运营同学也能维护。

### 5. 作为 brief schema 的来源

`达人brief框架拆解` 很适合沉淀成结构化 brief schema：

```json
{
  "brand_name": "",
  "product_name": "",
  "product_price": "",
  "launch_time": "",
  "marketing_goal": "",
  "budget": "",
  "campaign_period": "",
  "platform": "",
  "collaboration_form": "",
  "publish_window": "",
  "rights_requirements": "",
  "compliance_requirements": ""
}
```

未来当媒介输入“客户 brief”时，可以用这个 schema 先结构化，再去检索适合的话术。

### 6. 作为 RAG 知识，不建议直接 SFT

这份 Excel 里的话术多为模板和流程，不是自然对话上下文。直接进 SFT 可能会让模型学到过度模板化的话术。

更适合：

- RAG 检索
- few-shot 示例
- LLM 标注参考
- 模板推荐
- 人工审核时的标准答案参考

如果未来要进入 SFT，也应该转换成带上下文的 instruction 样本，例如：

```json
{
  "instruction": "你是媒介，请在询价原创视频合作时向达人收集报价、返点、档期和改价下单信息。",
  "input": {
    "platform": "抖音",
    "collaboration_form": "原创视频",
    "publish_window": "4月20日-4月23日"
  },
  "output": "..."
}
```

而不是直接把 Excel 单元格塞进 `agency_reply`。

## 建议实现方案

### Phase 1: 只做外部知识解析和结构化输出

新增：

```text
src/external_knowledge.py
scripts/import_external_knowledge.py
outputs/external_knowledge/
```

输出：

```text
external_templates.jsonl
external_taxonomies.jsonl
external_workflows.jsonl
external_brief_schema.json
external_import_report.md
```

MVP 不需要很复杂，先用 Python 标准库解析 xlsx zip/xml 即可，或者明确引入 `openpyxl` 作为可选依赖。

建议每条外部模板结构：

```json
{
  "knowledge_id": "ext_tpl_xxx",
  "knowledge_type": "talk_template",
  "template_source": "expert_seed",
  "source_file": "KolClaw达人标签&沟通话术.xlsx",
  "source_sheet": "商务沟通知识库-询价及沟通话术",
  "source_row": 2,
  "stage": "price_inquiry",
  "scene": "ask_price",
  "platform": null,
  "scenario": "原创视频",
  "template_text": "...",
  "slots": ["project_name", "product_name", "publish_window", "platform", "collaboration_form"],
  "notes": ""
}
```

### Phase 2: 把外部知识接入现有 pipeline

不要改变 WeFlow 主处理链路。新增一个可选参数：

```bash
python scripts/run_pipeline.py \
  --input-dir ./raw \
  --output-dir ./outputs \
  --external-knowledge-dir ./external_data
```

作用：

- pipeline 正常处理 WeFlow JSON。
- 如果提供 external knowledge，则额外加载 expert templates。
- 输出时分开：
  - `template_candidates.jsonl`: conversation mined, only trainable
  - `expert_template_candidates.jsonl`: Excel expert seed
  - `merged_template_index.jsonl`: 可选，供 RAG 使用

### Phase 3: 用外部知识增强标注

外部知识可用于：

- stage/scene 规则权重
- business relevance 词表
- LLM 标注 prompt 中的可选标签说明
- 人工审核页面里的参考模板

但不要让外部模板覆盖真实聊天样本的标签。建议规则是：

```text
真实聊天标签 = conversation evidence first
外部知识 = reference / fallback / retrieval context
```

## 下一步给 Claude Code 的具体任务建议

1. 先不要把 Excel 内容混入 `training_samples`。
2. 新增外部知识导入模块，输出独立 JSONL。
3. 先重点解析 4 个工作表：
   - `添加新好友常规workflow`
   - `添加新达人知识库`
   - `商务沟通知识库-询价及沟通话术`
   - `砍价话术场景`
4. 对这 4 个表做 sheet-level 映射：
   - workflow -> opening / identity_intro
   - 添加新达人 -> opening / interest_probe
   - 询价沟通 -> price_inquiry / brief_alignment
   - 砍价话术 -> price_negotiation
5. 输出 `external_templates.jsonl`，每条保留 `source_sheet` 和 `source_row`。
6. 后续再解析行业标签和达人画像标签，先别一次做太重。

## 验收标准

- 不影响当前 WeFlow pipeline。
- 当前 demo 仍然：
  - `training_samples = 0`
  - `template_candidates = 0`
  - `excluded_samples = 3`
- 新脚本能读取 Excel 并输出外部模板 JSONL。
- 外部模板每条都有来源追溯字段。
- 外部模板不会进入 `training_samples`。
- 外部模板和真实聊天模板可以通过 `template_source` 区分。

## 一个重要产品建议

这份 Excel 代表“资深媒介认为应该怎么说”，而 WeFlow 聊天代表“真实业务里实际怎么说”。两者价值不同：

- Excel：规范、完整、适合作为专家知识和标准答案。
- WeFlow：真实、口语化、能体现达人反应和推进效果。

系统最终应该同时保留两套证据，而不是强行合并成一类数据。这样未来做 RAG 时，可以同时检索：

```text
相似真实对话样本 + 专家推荐话术模板 + 当前场景标签
```

这会比单纯堆聊天记录更稳。

