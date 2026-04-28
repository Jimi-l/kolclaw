# KOLClaw 脚手架架构说明

## 核心流程

1. `CampaignBrief`
2. `StrategyTemplate`
3. `RetrievalPlan`
4. `CandidateCreator[]`
5. 带评分拆解的排序结果

## 服务边界

- `brief_structurer.py`
  将原始 brief 转成结构化 `CampaignBrief`。后续如果接入更强的解析器或模型，这里是主要替换点。

- `strategy_loader.py`
  从本地 JSON 加载策略模板。后续可以迁移到数据库、配置中心或内部服务。

- `retrieval_planner.py`
  根据 brief 和策略模板生成检索计划，包括过滤条件、关键词和排序优先级。

- `candidate_repository.py`
  抽象候选人数据来源。当前读取本地 JSON，后续可替换为星图、抖音扩量或多数据源聚合适配器。

- `scoring_engine.py`
  负责可解释、确定性的规则打分。

- `ranking_engine.py`
  先执行硬过滤，再执行软评分，最后输出排序和推荐等级。

- `pipeline_runner.py`
  负责把整个流程串起来，供 API 路由或后续编排层调用。

## 为什么这样拆分

当前脚手架把核心业务对象和流程服务拆开，是为了后续平滑接入：

- 更真实的 brief 解析器
- 真正的星图适配器
- 真正的抖音扩量适配器
- OCR / 图片分析能力
- 更复杂的排序模型或学习型评分模型

这样可以尽量减少对外层 API 契约的冲击，同时保留足够清晰的替换边界。
