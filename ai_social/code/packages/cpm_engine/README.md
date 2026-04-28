# cpm_engine

负责基于星图字段和截图提取结果，计算预估播放量、自然 CPM、预期 CPM 与商业化评估结果。

## 当前实现

- `apps/api/app/schemas/xingtu_cpm.py`
- `apps/api/app/services/xingtu_cpm_rules.py`
- `apps/api/app/services/xingtu_cpm_extraction.py`
- `apps/api/app/api/routes_xingtu_cpm.py`
- `apps/api/tests/test_xingtu_cpm.py`

## 输入

- 报价
- 自然 / 商单播放
- 图表点位
- 平台预期数据
- 截图解析输出

## 输出

- 主次流量池估计
- 商单能力等级
- 预估商单播放量
- 自然 / 预期 CPM
- 复核原因、置信度、调试因子

## 说明

算法已经在 API 和测试中可运行，但目前仍与 `xingtu_enrichment` 共用一部分截图解析代码。
