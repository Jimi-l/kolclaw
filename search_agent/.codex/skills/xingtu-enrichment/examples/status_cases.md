# Status Cases

## Case 1: 搜索无结果
```yaml
search_name_used: 示例达人B
match_confidence: low
match_reason: 未在星图搜索结果中找到可匹配达人
field_missing_list:
  - xingtu_id
  - xingtu_profile_url
enrichment_status: xingtu_not_found
next_action: retry_later
```

## Case 2: 未入驻星图
```yaml
search_name_used: 示例达人C
match_confidence: low
match_reason: 可确认达人存在，但未在星图中以可用创作者身份出现
field_missing_list:
  - xingtu_id
  - price_20s
  - price_20_60s
  - price_60s_plus
enrichment_status: xingtu_unregistered
next_action: done
```

## Case 3: 同名歧义
```yaml
search_name_used: 小A
match_confidence: low
match_reason: 搜索结果中存在多个同名达人，粉丝量与内容方向不足以唯一确认
field_missing_list:
  - xingtu_id
  - xingtu_profile_url
  - price_20s
  - price_20_60s
  - price_60s_plus
enrichment_status: ambiguous_match
next_action: manual_review
```

## Case 4: 部分字段缺失
```yaml
search_name_used: 示例达人D
match_confidence: high
match_reason: 名称、粉丝量、内容方向一致，身份可确认
field_missing_list:
  - monthly_connected_user_fan_ratio
  - monthly_deep_user_fan_ratio
enrichment_status: field_partial
next_action: done
```

## Case 5: 登录失效
```yaml
search_name_used: 示例达人E
match_confidence: low
match_reason: 星图会话失效，未完成搜索
field_missing_list:
  - xingtu_id
enrichment_notes: login_required
enrichment_status: blocked
next_action: retry_later
```
