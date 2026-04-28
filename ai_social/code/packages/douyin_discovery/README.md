# douyin_discovery

负责候选达人发现、搜索执行和结果行收集。

## 当前实现

- `apps/api/app/services/shortlist_runner.py`
- `apps/api/app/services/shortlist_search_planner.py`
- `apps/api/app/services/xingtu_selectors.py`
- `apps/api/app/services/xingtu_workflow.py`
- `apps/api/run_xingtu_flow.py`
- `apps/api/tests/test_xingtu_live_flow.py`

## 输入

- 搜索计划
- 星图工作台账号
- Playwright storage state
- 筛选条件

## 输出

- 结果行预览
- 候选达人详情页入口
- 采集 metadata
- collection errors

## 说明

仓库里“抖音巡号”当前是通过 Xingtu 兼容链路实现的最小发现能力，还没有独立的抖音 feed 巡号 / 爆款识别引擎。
