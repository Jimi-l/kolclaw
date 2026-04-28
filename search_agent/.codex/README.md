# search_agent /.codex

这是 `search_agent` 项目的本地 Codex 协作配置目录，用于约束 agent 的任务边界、执行方式、字段结构、标签体系与技能拆分。

## 目标

将 KOL 搜索与数据补齐流程拆成两个可独立调用的技能：

1. `creator-discovery`
   - 在抖音推荐流/候选视频中识别潜力达人
   - 提取基础数据
   - 完成人设、内容、场景、广告适配标签判断
   - 写入基础记录（不补星图字段）

2. `xingtu-enrichment`
   - 对待补齐达人进入星图检索
   - 匹配达人
   - 提取价格、预估播放、商单表现、涨粉等字段
   - 回填星图相关数据

## 使用顺序

Codex 在处理任何任务前，按以下顺序读取：

1. `project.md`
2. `workflow/search_agent_workflow.md`
3. `shared/rules/general.md`
4. 根据任务选择：
   - `skills/creator-discovery/SKILL.md`
   - 或 `skills/xingtu-enrichment/SKILL.md`
5. 再读取该 skill 下的 `docs/`、`prompts/`、`examples/`

## 目录说明

- `project.md`
  - 项目范围、目标、阶段划分、成功标准

- `prompts/`
  - 顶层路由与调度提示词
  - 用于判断当前任务应进入哪个 skill

- `shared/fields/`
  - 通用字段定义
  - 保证两个 skill 的输出结构兼容

- `shared/rules/`
  - 全局规则与技能专项规则
  - 包含去重、异常处理、禁止伪造、字段规范等

- `shared/tags/`
  - 标签体系
  - 主要供 `creator-discovery` 使用

- `workflow/`
  - 端到端流程文档
  - 描述 discovery → queue → enrichment → output 的状态流转

- `skills/`
  - 各技能的本地知识包
  - 每个 skill 下包含：
    - `SKILL.md`
    - `docs/`
    - `prompts/`
    - `examples/`

## 设计原则

1. 先拆分，再编排
   - 抖音巡号与星图补齐是两个阶段，不混成一个黑箱任务

2. 先保留原始值，再做标准化
   - 所有关键数值尽量同时保留 raw 与 normalized 两种表示

3. 可解释优先
   - 每条记录要能说清楚：为什么入选、为什么跳过、为什么补齐失败

4. 不伪造、不脑补
   - 看不到的数据不填
   - 不确认的匹配不回填

5. 小步闭环
   - discovery 输出标准记录
   - enrichment 只消费标准记录
   - 输出结构始终稳定

## 协作要求

- 默认使用中文写文档、注释、说明
- 代码中的字段名使用稳定英文 snake_case
- 不随意新增字段；若确需新增，必须同步更新：
  - `shared/fields/*`
  - skill 的 `docs/`
  - 对应 `examples/`

## 本地扩展建议

后续如果增加新技能，建议沿用同样结构：

- `skills/<skill-name>/SKILL.md`
- `skills/<skill-name>/docs/*`
- `skills/<skill-name>/prompts/*`
- `skills/<skill-name>/examples/*`

例如：

- `brief-parse`
- `creator-ranking`
- `outreach-prep`
- `feishu-sync`