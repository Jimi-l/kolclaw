# Creator Discovery Skill Package

## Package Purpose

把已经验证过的达人巡号业务流程，收敛为一个本地可运行、可扩展、可快速迭代的工作流包。

当前包重点解决的是：

- 让业务流程有清晰的本地结构
- 让发现流程与补数流程的字段边界清楚
- 让后续替换真实浏览器、飞书和平台 selector 时不需要推倒重来

## Main Capabilities

- 承载抖音推荐流发现 workflow skeleton
- 承载星图数据补齐 workflow skeleton
- 提供统一的数据模型和本地存储
- 提供浏览器、LLM、飞书的粗粒度接口
- 支持 mock mode，便于本地先跑通流程骨架

## Inputs

- 抖音侧浏览结果或页面提取结果
- 达人主页观察结果
- 星图搜索和详情页提取结果
- 运行配置（mock / live、目标数量、时长、数据目录）
- 既有达人记录（用于 merge/update）

## Outputs

- `VideoCandidate`
- `CreatorRecord`
- `XingtuRecord`
- `WorkflowSummary`
- 本地 SQLite 记录
- checkpoint / logs / screenshots

## Logical Skills

### `douyin_discovery`

职责：

- 登录抖音
- 浏览推荐流
- 快速跳过低价值内容
- 识别潜力视频
- 提取基础字段
- 触发达人分析
- 写入基础记录

输入：

- 推荐流页面状态
- 视频基础交互数据
- 达人主页观察结果

输出：

- `VideoCandidate`
- 不含星图字段的 `CreatorRecord`
- discovery workflow summary

### `ad_filtering`

职责：

- 快速识别广告、直播、低信号视频
- 将非候选内容尽快跳过
- 给出跳过原因，便于日志和后续调阈值

输入：

- 推荐流视频元数据
- 页面信号（广告字样、直播标识、互动量）

输出：

- `skip`
- `candidate`
- skip reason / threshold note

### `creator_tagging`

职责：

- 根据达人主页、近期视频、推荐视频上下文
- 生成人设标签、内容标签、场景标签
- 生成广告类型适配
- 保留自主新增标签及其判定依据

输入：

- 视频候选基础字段
- 达人主页分析上下文
- 规则约束（标签最多 2 个等）

输出：

- `persona_tags`
- `content_tags`
- `scene_tags`
- `ad_fit`
- `analysis_notes`

### `record_merge_update`

职责：

- 合并新发现记录和已有记录
- 保留已有星图字段
- 更新最新爆款视频和分析结果
- 避免重复创建达人

输入：

- existing `CreatorRecord`
- incoming `CreatorRecord` / `XingtuRecord`

输出：

- merged `CreatorRecord`
- `created` / `updated` status

### `xingtu_enrichment`

职责：

- 找出星图字段为空的达人
- 登录星图
- 搜索并匹配达人
- 提取商业化字段
- 回填并标记补齐状态

输入：

- 待补齐达人列表
- 星图搜索结果
- 星图详情页字段

输出：

- enriched `XingtuRecord`
- 更新后的 `CreatorRecord`
- enrichment workflow summary

## Suggested Execution Order

1. `douyin_discovery`
2. `ad_filtering`
3. `creator_tagging`
4. `record_merge_update`
5. `xingtu_enrichment`

## Current Boundary

这是首版骨架，不代表已经具备以下能力：

- 真实稳定 selector
- 生产级登录态保持
- 生产级飞书读写
- 生产级星图字段全量提取

这些都应该在当前结构上逐步替换，不需要重新设计主干。
