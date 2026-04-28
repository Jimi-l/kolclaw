# search_agent Workflow

## 一、总流程

`search_agent` 的标准工作流：

1. 接收任务
2. 顶层路由
3. 执行 creator-discovery 或 xingtu-enrichment
4. 输出结构化结果
5. 标记状态
6. 进入下一阶段或终止

---

## 二、主状态流转

```text
new_task
  ↓
routing
  ↓
creator-discovery
  ↓
discovered
  ↓
queued_for_xingtu
  ↓
xingtu-enrichment
  ↓
xingtu_completed

异常分支：

creator-discovery → skipped
creator-discovery → blocked

xingtu-enrichment → xingtu_not_found
xingtu-enrichment → xingtu_unregistered
xingtu-enrichment → ambiguous_match
xingtu-enrichment → field_partial
xingtu-enrichment → blocked
三、阶段说明
阶段 A：routing

判断任务应进入：

creator-discovery
xingtu-enrichment
或多阶段串行
阶段 B：creator-discovery

完成：

潜力视频识别
基础数据提取
标签分析
流量趋势判断
基础记录生成

输出状态：

discovered
或 queued_for_xingtu
阶段 C：queue

对于需要继续补齐的数据：

加入待补齐列表
保留 discovery 结构化输出
不直接混入 enrichment 结果
阶段 D：xingtu-enrichment

完成：

星图搜索
达人匹配
商业字段提取
状态回填

输出状态：

xingtu_completed
或异常状态
四、推荐任务拆法
场景 1：用户说“开始巡号”

执行：

routing → creator-discovery
discovery 输出标准记录
合格记录状态改为 queued_for_xingtu
场景 2：用户说“补齐星图”

执行：

routing → xingtu-enrichment
只读取状态为 queued_for_xingtu 的记录
完成回填
场景 3：用户说“整套跑完”

执行：

creator-discovery
discovery 结果去重
加入待补齐队列
xingtu-enrichment
输出完整结果
五、去重与合并
discovery 阶段去重

按以下顺序判断：

platform + creator_name
粉丝量量级
内容方向
头像或主页风格
enrichment 阶段去重

优先以：

xingtu_id
xingtu_profile_url

作为最终唯一锚点。

六、失败处理
阻塞型失败

需要停止当前阶段：

登录失效
验证码
数据源不可访问
表格不可写
非阻塞型失败

允许继续后续条目：

单条达人搜索失败
某字段没找到
单条视频不达标
单条记录匹配不稳
七、输出原则

每一阶段结束，必须至少输出：

当前阶段名称
处理数量
成功数量
跳过数量
阻塞数量
结构化结果或结构化状态列表
八、与后续系统的接口

当前 workflow 输出可以直接供未来模块消费：

ranking 模块
feishu-sync 模块
outreach 模块
reporting 模块

因此本 workflow 的字段与状态要保持稳定，不要频繁改名。


---