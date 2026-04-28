# Creator Discovery

**Project Status:** `prototype`

`creator-discovery` 是面向本地迭代的达人发现工作流骨架包。

这一版是 `v0 skeleton`，目标不是把抖音巡号和星图补数一次性做成生产系统，而是先把已经验证过的业务流程沉淀成可运行、可扩展、可继续细化的本地包：

- 保留两条核心业务链路
- 明确字段边界和责任归属
- 提供最小可运行的 workflow skeleton
- 为后续接入真实浏览器、LLM、飞书、多平台数据补齐留好扩展点

## Scope

当前包围绕两条流程展开：

1. `Douyin discovery workflow`
   - 抖音登录
   - 推荐流浏览
   - 广告 / 直播 / 低信号内容快速跳过
   - 潜力视频识别
   - 基础数据提取
   - 达人主页分析
   - 流量趋势判断
   - 标签生成
   - 写入不含星图字段的基础达人记录

2. `Xingtu enrichment workflow`
   - 获取星图字段为空的达人
   - 登录星图
   - 搜索达人并校验匹配
   - 提取商业化指标
   - 回填记录并更新补齐状态

## What This Version Includes

- `docs/`：流程说明、字段定义、阶段计划
- `prompts/`：五个粗粒度逻辑技能的提示词草案
- `tools/`：浏览器 runtime、LLM wrapper、飞书 stub、SQLite storage、数据模型、两条 workflow skeleton
- `tests/`：模型和规则的基础校验
- `data/`：本地运行时目录（checkpoint / screenshot / logs / cache）

## What This Version Deliberately Does Not Do

- 不实现生产级 selector
- 不实现生产级反爬 / stealth / anti-bot
- 不把模块拆得很深
- 不搭建完整 MCP 框架
- 不承诺真实飞书或星图接口已经打通

## Quick Start

```bash
cd /home/tuo/project/creator-discovery
python3 tools/douyin_workflow.py --mock --target-creators 2
python3 tools/xingtu_workflow.py --mock --limit 2
pytest
```

默认建议使用 mock mode 跑通骨架。真实接入时，优先替换：

- `tools/browser_runtime.py`
- `tools/feishu_client.py`
- `tools/llm_client.py`
- `tools/douyin_workflow.py` 中的 selector / extraction TODO
- `tools/xingtu_workflow.py` 中的搜索匹配 / 提取 TODO

## File Map

- `SKILL.md`：包用途、能力、输入输出、五个逻辑技能定义
- `docs/WORKFLOW.md`：两条工作流的业务拆解与运行边界
- `docs/FIELDS.md`：首版字段字典与 workflow ownership
- `docs/ITERATION_PLAN.md`：v0-v4 迭代路径

## Local Data Model

核心模型位于 `tools/models.py`：

- `VideoCandidate`
- `CreatorRecord`
- `XingtuRecord`
- `WorkflowSummary`

本地默认持久化使用 SQLite，数据库文件默认位于：

- `data/cache/creator_discovery.db`

## Next-Round Direction

下一轮最值得做的不是继续加模块，而是把真实页面交互逐步替换进现有骨架：

- 先让 Douyin 推荐流能本地稳定跑
- 再接飞书写回
- 再接 Xingtu 补数
- 最后做规则和提取精修
