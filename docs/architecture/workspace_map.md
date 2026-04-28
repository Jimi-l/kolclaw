# Workspace Map

这张图描述当前 `/home/tuo/project` 下各子项目的关系、状态和数据流。

```mermaid
flowchart TD
    ROOT[/home/tuo/project]

    ROOT --> AIS[ai_social\ncanonical product shell]
    ROOT --> SA[search_agent\ncanonical discovery runtime]
    ROOT --> CD[creator-discovery\nprototype]
    ROOT --> CDB[contact_db\ncanonical]
    ROOT --> MKF[media_knowledge_factory\ncanonical]
    ROOT --> MAW[media_annotation_workbench\ndownstream app]
    ROOT --> WC[we_chat\ncanonical data ingress]
    ROOT --> LEG[legacy/code_snapshot\nlegacy snapshot]

    AIS -->|brief parser / cpm engine / shortlist demo| SA
    SA -->|creator & xingtu outputs| AIS
    WC -->|db inspection / source understanding| CDB
    CDB -->|cleaned chats / samples| MKF
    MKF -->|snapshot outputs| MAW
    CD -. prototype references .-> SA
    LEG -. historical reference .-> AIS
```

## Project Roles

| Project | Status | Upstream | Downstream |
| --- | --- | --- | --- |
| `ai_social` | `canonical` | `search_agent` 的 discovery / enrichment 结果可回流到这里做 shortlist 与 CPM demo | 面向 demo、API、前端展示 |
| `search_agent` | `canonical` | 接受 brief/标签意图、浏览器登录态与任务配置 | 输出 discovery / xingtu enrichment 结果给 `ai_social` 或其他流程 |
| `creator-discovery` | `prototype` | 无强依赖，主要承载 prompt / skeleton | 给 `search_agent` 和业务设计提供原型参考 |
| `contact_db` | `canonical` | 可由 `we_chat` 导出的会话数据供给 | 为 `media_knowledge_factory` 提供结构化会话与模板候选 |
| `media_knowledge_factory` | `canonical` | 依赖 `contact_db` 输出和业务规则 | 产出知识快照给 `media_annotation_workbench` |
| `media_annotation_workbench` | `downstream app` | 消费 `media_knowledge_factory/outputs/seed_v1` | 输出审核结论与标注数据 |
| `we_chat` | `canonical` | 原始微信本地数据库 | 支撑 `contact_db` 路线判断与导出策略 |
| `legacy/code_snapshot` | `legacy snapshot` | 从 `/home/tuo/code` 导入 | 仅用于历史对照，不再继续开发 |
