# xingtu_enrichment

负责进入星图详情页、补齐达人字段，并从截图中抽取商业化相关数据。

## 当前实现

- `apps/api/app/schemas/xingtu.py`
- `apps/api/app/services/xingtu_runner.py`
- `apps/api/app/services/xingtu_workflow.py`
- `apps/api/app/services/xingtu_cpm_extraction.py`
- `apps/api/app/services/xingtu_cpm_vlm.py`
- `packages/xingtu_enrichment/docs/live_run.md`
- `packages/xingtu_enrichment/docs/workflow_notes.md`

## 输入

- 达人结果行
- 详情页 DOM / 文本
- 截图文件
- 本地登录态

## 输出

- `XingtuCreatorDetail`
- 归一化字段
- 字段来源
- warnings / missing fields

## 说明

这个模块已经具备最小可用的在线采集与截图解析链路，是当前仓库里最接近真实执行面的部分。
