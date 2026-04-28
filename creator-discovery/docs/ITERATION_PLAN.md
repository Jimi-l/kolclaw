# Iteration Plan

## v0 Skeleton

目标：

- 建好本地包结构
- 落下 workflow docs / field docs / prompts
- 提供模型、存储、runtime、workflow skeleton
- 可以通过 mock mode 跑通一轮 discovery / enrichment

交付：

- 当前目录结构
- SQLite 本地存储
- dataclass 模型
- mock browser / mock llm / feishu stub
- 基础测试

不做：

- 真实 selector
- 真实飞书写回
- 真实星图抓数

## v1 Local Runnable Discovery

目标：

- 让抖音 discovery 在本地浏览器里真正跑起来
- 能稳定进入推荐流
- 能完成广告 / 直播 / 低信号过滤
- 能抓到基础候选视频字段

重点工作：

- 接入真实浏览器驱动
- 打通登录态保存
- 实现推荐流浏览和基础字段提取
- 把 mock candidate 替换为真实 candidate

风险点：

- 页面 selector 漂移
- 视频播放控制不稳定
- 推荐流与详情页切换造成视野错位

## v2 Feishu Writeback

目标：

- 把本地记录与飞书多维表格打通
- discovery 结果能写回飞书

重点工作：

- 确认飞书读写模式
- 建立本地字段与飞书字段映射
- 增加去重和 update 策略
- 增加失败重试和基本审计日志

风险点：

- 字段类型不一致
- 飞书限流
- 重复写入或覆盖错误

## v3 Xingtu Enrichment

目标：

- 真正跑通星图补数流程
- 可以对待补齐达人逐个搜索并回填商业字段

重点工作：

- 打通星图登录态
- 实现达人搜索和匹配
- 实现字段提取与截图
- 回填本地记录与飞书记录

风险点：

- 匹配歧义
- 部分达人未入驻
- 页面字段位置变化

## v4 Refinement

目标：

- 提升稳定性、准确率、可观察性
- 把高频自主新增标签收敛到规则库

重点工作：

- 优化阈值和跳过策略
- 完善流量趋势和标签规则
- 增加 checkpoint 恢复
- 增加更细的异常分类和日志
- 视需要引入更完整的 runtime / orchestration

衡量标准：

- discovery 命中率更稳定
- 重复达人处理更稳
- xingtu 字段缺失率下降
- 人工复核成本下降
