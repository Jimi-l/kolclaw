# brief_parser

负责把原始 brief 解析成仓库内可消费的结构化需求。

## 当前实现

- `apps/api/app/schemas/brief_parse.py`
- `apps/api/app/services/brief_parse_interface.py`
- `apps/api/app/services/brief_structurer.py`
- `apps/api/app/services/shortlist_brief_parser.py`
- `apps/api/app/api/routes_brief.py`
- `apps/api/tests/test_brief_parse_contract.py`
- `packages/brief_parser/docs/*`

## 输入

- 原始 brief 文本
- `BriefParseInput`
- 已存在的结构化 brief

## 输出

- `BriefParseOutput`
- `ShortlistRequirement`
- `parser_notes`
- 缺失信息、歧义、优先级信号

## 说明

当前运行时代码仍位于 `apps/api`，这个包目录主要承担模块归档、文档承载和后续独立抽包的边界声明。
