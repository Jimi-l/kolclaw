# KOLClaw

KOLClaw 是一个面向抖音 / 巨量星图媒介流程的 AI 工具仓库。当前可运行部分主要是 `apps/api` 和 `apps/web`，同时已经按业务边界整理出适合继续演进的 monorepo 结构，便于后续把模块从单体 API 中逐步拆成独立 package。

当前主链路覆盖：

`Brief 解析 -> 达人标签匹配 -> 抖音 / 星图发现 -> 星图补充 -> CPM 计算 -> shortlist 输出`

`contact_knowledge` 目前仍是文档和技能占位，还没有单独的 API 或存储实现。

**Workspace Status:** `canonical subproject inside /home/tuo/project/ai_social`

## Monorepo 结构

```text
.
├── apps/
│   ├── api/                      # FastAPI backend
│   └── web/                      # React + Vite demo frontend
├── configs/                      # 策略模板
├── data/
│   ├── mock_briefs/              # 仓库内可提交的 mock 数据
│   ├── mock_candidates/          # 仓库内可提交的 mock 数据
│   ├── private/                  # 仅存放仍需本地隔离的私密数据
│   └── xingtu_cpm/real_images/   # 可进入私有仓库的真实截图 fixture
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   └── module_map.md
│   └── contracts/                # 迁移索引页
├── examples/                     # 仓库内样例输入输出
├── local_only/                   # 仅保留本地 env / secret
├── runtime/                      # 可提交的调试运行产物与截图
├── packages/
│   ├── brief_parser/
│   ├── creator_tagging/
│   ├── douyin_discovery/
│   ├── xingtu_enrichment/
│   ├── cpm_engine/
│   ├── contact_knowledge/
│   └── common/
└── README.md
```

## 当前模块

| 模块 | 包目录 | 当前主要实现位置 | 输入 | 输出 | 状态 |
| --- | --- | --- | --- | --- | --- |
| `brief_parser` | `packages/brief_parser` | `apps/api/app/services/brief_parse_interface.py`, `brief_structurer.py`, `shortlist_brief_parser.py`, `apps/api/app/schemas/brief_parse.py` | 原始 brief 文本、结构化 brief 输入 | `BriefParseOutput`、`ShortlistRequirement`、解析说明 | 已实现 |
| `creator_tagging` | `packages/creator_tagging` | `apps/api/app/services/shortlist_search_planner.py`, `shortlist_scoring.py`，以及包内业务文档 | 结构化 brief、品类/人群/调性约束 | 标签方向、筛选意图、偏好和排除条件 | 部分实现，文档先行 |
| `douyin_discovery` | `packages/douyin_discovery` | `apps/api/app/services/shortlist_runner.py`, `shortlist_search_planner.py`, `xingtu_selectors.py`, `xingtu_workflow.py`, `apps/api/run_xingtu_flow.py` | 搜索计划、登录态、筛选条件 | 发现到的达人行、候选详情入口、收集错误 | 已实现最小可用链路 |
| `xingtu_enrichment` | `packages/xingtu_enrichment` | `apps/api/app/services/xingtu_runner.py`, `xingtu_workflow.py`, `xingtu_cpm_extraction.py`, `xingtu_cpm_vlm.py`, `apps/api/app/schemas/xingtu.py` | 达人行、详情页、截图集合 | `XingtuCreatorDetail`、截图字段提取结果、字段来源与 warning | 已实现 |
| `cpm_engine` | `packages/cpm_engine` | `apps/api/app/services/xingtu_cpm_rules.py`, `xingtu_cpm_extraction.py`, `apps/api/app/schemas/xingtu_cpm.py`, `apps/api/app/api/routes_xingtu_cpm.py` | 归一化后的星图指标或截图解析结果 | 预估播放量、自然 CPM、预期 CPM、CPE/CPM 评估、复核标记 | 已实现 |
| `contact_knowledge` | `packages/contact_knowledge` | `.codex/skills/outreach-draft/SKILL.md`, `.codex/agents/outreach-drafting-agent.md` | shortlist、建联背景、聊天记录 | 话术草稿、结构化聊天摘要、待跟进事项 | 规划中 |
| `common` | `packages/common` | `packages/common/schemas`, `apps/api/app/core/config.py`, `apps/api/app/utils/*` | 跨模块 schema、配置、工具函数 | 公共 schema、路径解析、数值归一化工具 | 已实现 |

说明：当前 monorepo 已经把模块目录和文档边界整理出来，但运行时代码还主要集中在 `apps/api`。这次整理刻意避免大规模重构，以保证现有功能不被打断。

## 本地运行

### 1. Python API

```bash
cd /home/tuo/project/ai_social/code
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api
uvicorn main:app --reload
```

API 默认地址：`http://127.0.0.1:8000`

### 2. Web Demo

```bash
cd /home/tuo/project/ai_social/code/apps/web
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:5173`

### 3. 环境变量

- 仓库根目录提供了 `.env.example`
- 本地真实配置应放在仓库根目录 `.env`，或 `local_only/env/apps_api.env`
- `apps/api/app/services/xingtu_cpm_vlm.py` 会自动读取上述本地 env 文件
- `XINGTU_CPM_DEBUG_RUN_LOG_DIR` 默认写入 `runtime/debug_runs/xingtu_cpm`

### 4. 测试

```bash
cd /home/tuo/project/ai_social/code
.venv/bin/python -m unittest discover -s apps/api/tests -v
```

## 模块输入输出

### `brief_parser`

- 输入：原始 brief 文本、`BriefParseInput`
- 输出：`BriefParseOutput`、`ShortlistRequirement`、`parser_notes`

### `creator_tagging`

- 输入：结构化 brief、品类/人群/内容风格约束
- 输出：标签方向、筛选器映射、偏好项、排除项、人工复核点

### `douyin_discovery`

- 输入：搜索计划、星图工作台账号、storage state、命名筛选条件
- 输出：候选达人结果行、达人详情入口、收集过程 metadata

### `xingtu_enrichment`

- 输入：达人详情页、星图截图、已有达人行数据
- 输出：`XingtuCreatorDetail`、VLM 提取字段、字段来源、缺失字段

### `cpm_engine`

- 输入：播放量、报价、近 30 天发文数、图表点位、VLM 提取结果
- 输出：流量池估计、预估商单播放、自然 / 预期 CPM、置信度、复核原因

### `contact_knowledge`

- 输入：已确认 shortlist、建联目标、聊天上下文、历史话术
- 输出：微信 / 企微话术、聊天记录结构化摘要、跟进建议

### `common`

- 输入：跨模块 schema 需求、路径配置、归一化工具需求
- 输出：共享 schema、配置对象、数值解析与工具函数

## 不能推送到 GitHub 的内容

以下内容已经被整理到本地专用目录或应被 `.gitignore` 忽略：

- `local_only/`
  - 本地 API key / env / token / cookie / storage state
- `data/private/`
  - 仍需本地隔离的私密素材
- `runtime/`
  - 可提交的真实调试运行产物与截图
- `data/xingtu_cpm/real_images/`
  - 可提交的真实星图截图 fixture
- `.env`、`.env.*`
- `.venv/`
- `apps/web/node_modules/`
- `apps/web/dist/`
- `__pycache__/`、`.pytest_cache/`

如果你准备初始化 Git 仓库，请先确认 `local_only/`、`data/private/` 和根目录 `.env` 没有被纳入暂存区。

## 参考文档

- 模块链路图：`docs/architecture/module_map.md`
- 旧版架构说明：`docs/architecture/overview.md`
- 示例文件：`examples/`
