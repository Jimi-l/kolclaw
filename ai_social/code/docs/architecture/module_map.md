# Module Map

## 目标链路

```text
Raw Brief
  -> brief_parser
  -> creator_tagging
  -> douyin_discovery
  -> xingtu_enrichment
  -> cpm_engine
  -> contact_knowledge
```

## 当前仓库中的对应关系

### 1. Brief 解析

- 包目录：`packages/brief_parser`
- 当前实现：
  - `apps/api/app/services/brief_parse_interface.py`
  - `apps/api/app/services/brief_structurer.py`
  - `apps/api/app/services/shortlist_brief_parser.py`
  - `apps/api/app/schemas/brief_parse.py`
  - `apps/api/app/api/routes_brief.py`
- 输入：
  - 原始 brief 文本
  - `BriefParseInput`
- 输出：
  - `BriefParseOutput`
  - `ShortlistRequirement`
  - 缺失信息、歧义、优先级信号

### 2. 达人标签匹配

- 包目录：`packages/creator_tagging`
- 当前实现：
  - `apps/api/app/services/shortlist_search_planner.py`
  - `apps/api/app/services/shortlist_scoring.py`
  - `packages/creator_tagging/docs/*`
- 输入：
  - 结构化 brief
  - 品类、人群、调性、排除项
- 输出：
  - 标签方向
  - 命名筛选器映射
  - 偏好项 / 排除项
  - 人工复核点

### 3. 抖音巡号 / 发现

- 包目录：`packages/douyin_discovery`
- 当前实现：
  - `apps/api/app/services/shortlist_runner.py`
  - `apps/api/app/services/shortlist_search_planner.py`
  - `apps/api/app/services/xingtu_selectors.py`
  - `apps/api/app/services/xingtu_workflow.py`
  - `apps/api/run_xingtu_flow.py`
- 输入：
  - 搜索计划
  - 账号登录态
  - 星图筛选条件
- 输出：
  - 结果行预览
  - 目标达人详情页入口
  - 发现阶段错误和 metadata

说明：当前“抖音巡号”实际是通过星图兼容工作流落地的最小可用链路，还没有独立的抖音 feed 巡号引擎。

### 4. 星图补充

- 包目录：`packages/xingtu_enrichment`
- 当前实现：
  - `apps/api/app/services/xingtu_runner.py`
  - `apps/api/app/services/xingtu_workflow.py`
  - `apps/api/app/services/xingtu_cpm_extraction.py`
  - `apps/api/app/services/xingtu_cpm_vlm.py`
  - `apps/api/app/schemas/xingtu.py`
- 输入：
  - 达人详情页
  - 星图截图
  - 结果行基础字段
- 输出：
  - `XingtuCreatorDetail`
  - VLM / OCR 提取字段
  - 字段来源、warning、缺失字段

### 5. CPM 计算

- 包目录：`packages/cpm_engine`
- 当前实现：
  - `apps/api/app/services/xingtu_cpm_rules.py`
  - `apps/api/app/services/xingtu_cpm_extraction.py`
  - `apps/api/app/schemas/xingtu_cpm.py`
  - `apps/api/app/api/routes_xingtu_cpm.py`
- 输入：
  - 报价
  - 自然 / 商单播放量
  - 发文数
  - 图表点位
  - 平台预期数据
- 输出：
  - 主次流量池
  - 商单能力等级
  - 预估播放量
  - 自然 CPM / 预期 CPM / 分档 CPM
  - 置信度与复核原因

### 6. 建联话术库

- 包目录：`packages/contact_knowledge`
- 当前实现：
  - `.codex/skills/outreach-draft/SKILL.md`
  - `.codex/agents/outreach-drafting-agent.md`
- 输入：
  - 已确认 shortlist
  - campaign summary
  - 联系人上下文
  - 聊天记录
- 输出：
  - 微信 / 企微建联话术
  - 结构化聊天摘要
  - 待跟进动作

说明：该模块目前没有单独 API、数据库或知识库目录，属于“包目录已预留、运行时待补”的状态。

## 横向公共层

- 包目录：`packages/common`
- 当前实现：
  - `packages/common/schemas/*`
  - `apps/api/app/core/config.py`
  - `apps/api/app/utils/*`

该层为所有业务模块提供：

- 共享 schema 样例
- 路径与工作区配置
- 数值解析 / 归一化工具
- 通用调试与文件约定
