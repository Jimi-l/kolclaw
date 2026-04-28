# AI Media Operations Monorepo

`/home/tuo/project` 是当前对内使用的私有 monorepo 根目录，覆盖达人发现、星图补数、CPM 估算、建联知识沉淀与审核工作台几条主链路。

这次整理的目标是先把现有项目纳入同一个仓库边界，补清目录职责、模块归属、运行方式和 secret 规则，不做大规模代码合并或接口重写。

## Workspace Layout

```text
/home/tuo/project
├── ai_social/                    # 主产品壳，含 brief / shortlist / CPM / 星图 demo
├── search_agent/                 # Discovery / enrichment 运行时主线
├── creator-discovery/            # Prompt-first workflow skeleton
├── contact_db/                   # 建联会话清洗与话术样本沉淀
├── media_knowledge_factory/      # 知识资产工厂
├── media_annotation_workbench/   # 审核与标注工作台
├── we_chat/                      # 微信本地数据库入口与探查
├── legacy/
│   └── code_snapshot/            # 从 /home/tuo/code 导入的只读历史快照
└── docs/
    └── architecture/
```

## Subprojects

| Project | Status | Responsibility |
| --- | --- | --- |
| `ai_social` | `canonical` | 当前主产品壳。`ai_social/code` 是 `brief_parser`、`cpm_engine`、shortlist demo 的主实现。 |
| `search_agent` | `canonical` | 当前更成熟的 discovery / enrichment 运行时。`douyin_discovery`、运行时 `creator_tagging`、运行时 `xingtu_enrichment` 以这里为主。 |
| `creator-discovery` | `prototype` | 保留为 prompt-first、skeleton-first 的流程原型，不是第一优先运行时。 |
| `contact_db` | `canonical` | 微信 / 企微建联会话清洗、训练样本构建、模板候选沉淀。 |
| `media_knowledge_factory` | `canonical` | 在 `contact_db` 基础上继续产出 brief 卡片、谈判 episode、检索切片、规则卡。 |
| `media_annotation_workbench` | `downstream app` | 消费知识工厂快照，提供审核、标注、导入、权限管理能力。 |
| `we_chat` | `canonical` | 微信本地数据库入口与只读探查脚本。 |
| `legacy/code_snapshot` | `legacy snapshot` | 从 `/home/tuo/code` 导入的历史版本，仅归档，不承接新功能。 |

## Module Ownership

| Module | Canonical Project | Current Main Paths | Input | Output |
| --- | --- | --- | --- | --- |
| `brief_parser` | `ai_social/code` | `apps/api/app/services/brief_*`, `apps/api/app/schemas/brief_parse.py`, `packages/brief_parser/` | 原始 brief 文本、结构化 brief | `BriefParseOutput`、`ShortlistRequirement`、解析说明 |
| `creator_tagging` | `search_agent` | `search_agent/tagging/`, `ai_social/code/packages/creator_tagging/`, `creator-discovery/prompts/creator_tagging.md` | 结构化 brief、行业/品类/风格约束 | 标签、匹配方向、筛选偏好、排除条件 |
| `douyin_discovery` | `search_agent` | `search_agent/adapters/douyin/`, `creator-discovery/tools/douyin_workflow.py` | 浏览器登录态、巡号规则、候选来源 | 视频候选、达人基础信息、巡号过程产物 |
| `xingtu_enrichment` | `search_agent` | `search_agent/adapters/xingtu/`, `ai_social/code/apps/api/app/services/xingtu_*`, `creator-discovery/tools/xingtu_workflow.py` | 达人候选、星图搜索页、截图 | 星图字段、商业指标、截图抽取结果 |
| `cpm_engine` | `ai_social/code` | `apps/api/app/services/xingtu_cpm_*`, `apps/api/app/schemas/xingtu_cpm.py`, `packages/cpm_engine/` | 星图指标、截图 OCR/VLM 结果 | 预估播放量、自然 CPM、预期 CPM、CPE/CPM 判断 |
| `contact_knowledge` | `contact_db` + `media_knowledge_factory` + `we_chat` | `contact_db/src/`, `media_knowledge_factory/src/`, `we_chat/scripts/` | 聊天记录、微信 DB、brief 与建联上下文 | 话术样本、知识卡、检索切片、审核队列 |
| `common` | shared concept | `ai_social/code/packages/common/`, `search_agent/{models,utils,storage,config}.py` | 跨模块 schema、配置、工具函数 | 共享 schema、路径约定、基础工具 |

详见 [docs/architecture/module_map.md](./docs/architecture/module_map.md) 和 [docs/architecture/workspace_map.md](./docs/architecture/workspace_map.md)。

## Local Run

### `ai_social`

```bash
cd /home/tuo/project/ai_social/code
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api
uvicorn main:app --reload
```

前端：

```bash
cd /home/tuo/project/ai_social/code/apps/web
npm install
npm run dev
```

### `search_agent`

```bash
cd /home/tuo/project/search_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

### `creator-discovery`

```bash
cd /home/tuo/project/creator-discovery
python3 tools/douyin_workflow.py --mock --target-creators 2
python3 tools/xingtu_workflow.py --mock --limit 2
pytest
```

### `contact_db`

```bash
cd /home/tuo/project/contact_db
python3 scripts/run_pipeline.py --input-dir . --output-dir ./outputs --prefix demo
```

### `media_knowledge_factory`

```bash
cd /home/tuo/project
python3 media_knowledge_factory/scripts/run_factory.py
pytest media_knowledge_factory/tests/test_pipeline.py
```

### `media_annotation_workbench`

后端：

```bash
cd /home/tuo/project/media_annotation_workbench/apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

前端：

```bash
cd /home/tuo/project/media_annotation_workbench/apps/web
npm install
npm run dev
```

### `we_chat`

```bash
cd /home/tuo/project/we_chat
python3 scripts/inspect_wechat_dbs.py --data-dir /home/tuo/project/we_chat/data --sample-rows 3
```

## What Can And Cannot Be Committed

允许进入私有仓库：

- 真实业务截图、真实聊天 JSON、真实微信 DB、真实知识快照、真实 runtime 输出
- `contact_db/data`、`we_chat/data`、`media_knowledge_factory/outputs` 这类业务数据
- `ai_social/code/runtime` 下不含 secret 的调试结果和截图

绝对不要提交：

- 任意 `.env`、`.env.*`、明文 API key
- Playwright / Chromium 登录态、cookie、storage state、浏览器 profile
- bearer token、会话凭据、签名 URL、带 `msToken` 或同类临时凭据的导出文件

当前已按 `.gitignore` 屏蔽的重点路径：

- `**/.env`
- `**/.env.*`
- `**/playwright/.auth/`
- `**/browser_state/`
- `search_agent/runtime/`
- `ai_social/code/local_only/env/`

说明：虽然私有仓库允许放真实业务数据，但 `search_agent/runtime/` 当前混合了浏览器登录态与会话相关产物，尚未拆分成“可提交输出”和“本地私密状态”两层，所以暂时整体保持本地隔离。

## Legacy Snapshot

`legacy/code_snapshot/` 是从 `/home/tuo/code` 导入的只读历史快照，用于保留旧版实现和文档上下文。它不参与当前接口兼容承诺，也不应再作为主运行目录继续开发。
