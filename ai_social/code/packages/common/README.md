# common

负责跨模块复用的 schema、配置和工具函数。

## 当前实现

- `packages/common/schemas/*`
- `apps/api/app/core/config.py`
- `apps/api/app/utils/normalization.py`
- `apps/api/app/utils/xingtu_units.py`

## 输入

- 路径配置需求
- 通用 schema 样例需求
- 数值 / 文本归一化需求

## 输出

- 共享 schema 样例
- 工作区路径解析
- 数值单位换算和归一化工具

## 说明

当前很多 Pydantic runtime schema 仍在 `apps/api/app/schemas/`，后续如果需要进一步拆包，可以把跨模块可复用部分逐步迁入 `packages/common`。
