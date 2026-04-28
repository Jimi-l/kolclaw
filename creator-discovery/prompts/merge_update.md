# Merge Update Prompt

## Role

你负责合并新记录与已有记录，避免重复达人。

## Goal

在保留已有有效字段的前提下，把新的 discovery 或 enrichment 结果并入现有 `CreatorRecord`。

## Merge Principles

1. `creator_name` 是首版主键候选
2. 有效的新视频信息可以覆盖旧的视频信息
3. 已有 `XingtuRecord` 不能被空值覆盖
4. 标签合并后仍需遵守数量约束
5. 冲突字段要记录到 `analysis_notes` 或 workflow log

## Preferred Precedence

- Discovery 更新 discovery-owned fields
- Xingtu enrichment 更新 xingtu-owned fields
- Shared/system fields 由 storage 统一维护

## Output Contract

```json
{
  "status": "created_or_updated",
  "creator_record": {},
  "merge_notes": []
}
```
