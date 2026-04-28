# creator_tagging

负责把结构化 brief 转成达人标签、筛选方向和匹配规则。

## 当前实现

- `packages/creator_tagging/docs/*`
- `apps/api/app/services/shortlist_search_planner.py`
- `apps/api/app/services/shortlist_scoring.py`
- `.codex/skills/creator-tagging/SKILL.md`

## 输入

- `BriefParseOutput`
- `ShortlistRequirement`
- 品类、人群、内容风格、地域和排除项

## 输出

- 搜索方向标签
- 命名筛选器映射
- 偏好项和排除项
- 人工复核点

## 说明

该模块当前以“文档先行 + 运行时嵌入 shortlist 服务”的方式存在，还没有完全抽成独立服务层。
