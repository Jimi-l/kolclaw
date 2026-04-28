# Skip Cases

## Case 1: 广告内容
```yaml
decision: skip
reason: 达人名称后带广告标识，属于投放内容，不作为自然巡号候选
status: skipped
next_action: skip
````

## Case 2: 直播间

```yaml
decision: skip
reason: 页面为直播间，不进入普通短视频分析链路
status: skipped
next_action: skip
```

## Case 3: 数据不达标

```yaml
decision: skip
reason: 点赞、评论、收藏、转发均未达到潜力阈值
status: skipped
next_action: skip
```

## Case 4: 主页判断失败

```yaml
decision: manual_review
reason: 进入主页后页面状态异常，无法稳定定位推荐视频与最新3条内容
status: blocked
next_action: manual_review
```

## Case 5: 重复达人

```yaml
decision: skip
reason: 当前达人已存在记录，且不是新的爆款视频
status: skipped
next_action: skip
```

## Case 6: 达人身份模糊

```yaml
decision: manual_review
reason: 达人名称提取不稳定，主页昵称与视频页显示存在明显歧义
status: blocked
next_action: manual_review
```

````
