# V1 媒介短名单 Demo 说明

## 目标

这一版只做一个窄但完整的演示链路：

1. 输入 brief
2. 解析为结构化需求
3. 生成面向星图的搜索计划
4. 执行现有星图自动化流程
5. 采集一小批达人详情
6. 做启发式评分与排序
7. 输出可读的短名单结果

本版明确不做：

- 抖音推荐流自主巡号
- 飞书回填
- 企业微信触达
- 返点和媒介执行闭环
- 多平台身份打通
- 完整 AI 媒介代理平台

## 主要代码位置

- `apps/api/app/schemas/shortlist.py`
  V1 短名单请求、需求对象、搜索计划、评分结果、返回结构

- `apps/api/app/services/shortlist_brief_parser.py`
  brief 解析器，负责把原始文本转成结构化需求

- `apps/api/app/services/shortlist_search_planner.py`
  把结构化需求映射成星图搜索计划

- `apps/api/app/services/shortlist_scoring.py`
  V1 启发式评分器

- `apps/api/app/services/shortlist_runner.py`
  串起解析、搜索计划、星图采集、排序输出

- `apps/api/app/services/reference_docs_loader.py`
  外部参考文档索引，不做 RAG，只做元数据发现

- `apps/api/app/api/routes_shortlist.py`
  V1 短名单接口

- `apps/web/src/pages/DemoPage.tsx`
  前端演示页

## 参考文档使用边界

V1 主要参考 `external_docs/operational` 下的执行文档。

这些文档的作用是：

- 约束 V1 的媒介工作流顺序
- 提供标签、选号、星图字段的命名参考
- 提供初版评分启发式

这些文档当前不用于：

- 构建知识库检索系统
- 驱动开放式智能体决策
- 扩大产品边界到全自动媒介平台

## API

### 1. 获取 V1 参考文档

`GET /api/shortlist/references`

### 2. 解析 brief

`POST /api/shortlist/parse`

请求示例：

```json
{
  "raw_text": "Brand: Luminelle\nProduct: Velvet Lip Glaze\nBudget: 80000 RMB\nTarget audience: female office workers\nStyle: polished beauty tutorial\nTone: premium\nAvoid: parenting, pets"
}
```

### 3. 预览搜索计划

`POST /api/shortlist/plan`

### 4. 运行实时短名单

`POST /api/shortlist/run`

请求示例：

```json
{
  "raw_text": "Brand: Luminelle\nProduct: Velvet Lip Glaze\nSKU: V06\nPlatform: douyin\nCity: shanghai\nBudget: 80000 RMB\nTarget audience: female office workers, beauty shoppers\nKPI: stable views, completion rate, cost efficiency\nStyle: polished beauty tutorial, seeding\nTone: premium, trustworthy\nAvoid: parenting, pets\nMust: beauty creators with female audience\nPrefer: shanghai-based creators with recent growth",
  "account_name": "Demo Workspace Account 001",
  "collection_limit": 5,
  "shortlist_limit": 3,
  "headless": true
}
```

说明：

- `storage_state_path` 不传时，会默认尝试工作区下的 `playwright/.auth/xingtu.json`
- `account_name` 建议在需要选择工作台账号入口时传入

## 运行方式

### 后端

```bash
cd /home/tuo/project/ai_social/code/apps/api
/home/tuo/project/ai_social/code/.venv/bin/uvicorn main:app --reload
```

### 前端

```bash
cd /home/tuo/project/ai_social/code/apps/web
npm install
npm run dev
```

前端打开后，按顺序使用：

1. `Parse Requirement`
2. `Preview Search Plan`
3. `Run Live Shortlist`

## 当前评分逻辑

V1 评分只做第一版启发式：

- `brief_match`
- `audience_match`
- `content_fit`
- `quality_activity`
- `commercial_signal`
- `risk_penalty`

输出内容包括：

- 总分
- 推荐级别
- 推荐理由
- 风险标记
- 解释字段

## 当前已知限制

- 当前最稳定的星图下拉筛选仍然是 `美妆 -> 美妆测评种草`
- 城市、粉丝门槛、预算上限等部分约束，当前仍以“采集后排序/过滤”为主
- 详情页字段仍有一部分依赖整页文本回退解析
- 结果列表和详情页 DOM 结构变化时，仍需要继续收紧选择器

## 建议的下一步

1. 为更多类目补稳定的星图筛选映射
2. 收紧达人列表行结构选择器，补更多列级字段
3. 提升 brief 解析器对显式 `hard / preferred / negotiable` 段落的识别
4. 在评分前补更清晰的“硬过滤命中原因”输出
