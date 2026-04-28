# Annotation Guideline

## 1. 目标

本指南用于人工复核以下资产：

- `brief_cards.jsonl`
- `negotiation_episodes.jsonl`
- `talk_templates.jsonl`
- `retrieval_chunks.jsonl`

V1 重点不是人工逐条审全量消息，而是优先审核高价值 scene：

- brief
- 砍价
- 返点
- 档期
- 付款
- 入库
- 执行
- 返点追回

## 2. 证据要求

- 每个 `NegotiationEpisode` 必须引用 `evidence_message_ids`。
- 每个达人特征标签必须带 `confidence` 和 `evidence_message_ids`。
- 如果没有明确证据，标签必须打成 `unknown`，不能凭经验脑补。
- `TalkTemplate` 只能来自真实消息或人工种子卡，禁止自由编写无来源模板。

## 3. Episode 标注步骤

1. 先看该段消息围绕的单一业务目标。
2. 再定 `workflow_stage`，不要按单条消息机械切分。
3. 找出主 objection，只保留最影响推进的一个。
4. 标记媒介策略和达人响应方式。
5. 回填商业状态字段：价格、返点、付款阻塞、权益缺口。
6. 若达人是否缺单、强边界、回复风格不明确，一律标 `unknown`。

## 4. Workflow Stage

- `cold_outreach`：首次冷启动触达达人，目标是拿到回复或建立联系。
- `contact_established`：已建立基础联系，如通过好友验证、确认沟通窗口。
- `brief_delivery`：媒介向达人发送合作背景、需求和待确认项。
- `quote_collection`：达人返回报价、返点、档期、权益、合作须知。
- `rights_negotiation`：围绕授权、分发、二创、置顶、保留时长等权益协商。
- `price_negotiation`：围绕刊例价、水下价、打包价、改价进行谈判。
- `rebate_negotiation`：围绕返点目标、返点补差、服务费压力进行谈判。
- `schedule_lock`：围绕档期、锁档、定金、发布时间风险进行推进。
- `cooperation_confirmation`：双方确认合作意向、合作成立或锁定合作。
- `supplier_onboarding`：收集入库、营业执照、收款、发票、账号等资料。
- `payment_push`：催款、请款、下单、尾款、定金等支付推进。
- `execution_followup`：拉执行群、推进制作、脚本、交付、发布准备。
- `revision_coordination`：围绕修改次数、重拍、脚本调整、额外要求沟通。
- `publication_confirmation`：确认发布动作、发布时间、平台挂载和上线结果。
- `data_feedback`：围绕播放、互动、保量、投放维护、数据回传沟通。
- `rebate_recovery`：围绕返点回收、返点打款、返点材料和打款凭证推进。
- `repeat_collaboration`：复购或再次合作的延展沟通。

## 5. Episode Goal

- `get_reply`：拿到达人回复或确认后续沟通入口。
- `collect_quote`：拿到完整报价、返点、权益和档期。
- `raise_rebate`：把返点提升到目标线附近。
- `cut_price`：争取降价或用权益换价。
- `secure_schedule`：确保达人能留档并满足发布时间。
- `confirm_rights`：确认分发、授权、二创、置顶、保留时长等权益。
- `collect_docs`：收集入库、开票、收款、主体证明等资料。
- `lock_execution`：确认合作、拉执行、推进制作与交付。
- `push_payment`：推动定金、尾款或正式下单完成。
- `confirm_publish`：确认内容已发布或具备发布条件。
- `collect_data`：催数据回传、维护数据或解释数据表现。
- `recover_rebate`：追回返点并拿到打款凭据。

## 6. Objection Type

- `price_too_high`：客户或媒介认为报价偏高，需要砍价。
- `rebate_below_target`：当前返点低于媒介目标，影响利润或服务费。
- `no_free_distribution`：免费分发平台不满足要求。
- `rights_limited`：授权、投流、保留期等权益受限。
- `schedule_risk`：档期、制作周期、留档方式导致发布时间风险。
- `payment_rule_rigid`：付款、请款、下单规则僵硬，阻塞合作推进。
- `document_missing`：营业执照、入库、开票或收款资料不全。
- `cannot_guarantee_metrics`：达人无法保量、保赞或解释数据。
- `no_secondary_creation`：达人不接受二创、二剪等再创作要求。
- `platform_rule_rigid`：平台或公司规则强约束，难以灵活变通。
- `none`：该 episode 不存在明显 objection。

## 7. Talk Template 过滤标准

- 保留：可复用、可参数化、业务明确、带证据的媒介话术。
- 删除：纯寒暄、纯情绪宣泄、一次性噪音、表情占主导、无业务信息的短句。
- 长表单类消息可保留，但必须能明确归入 `brief_framework` 或 `fulfillment_sop`。

## 8. Retrieval Chunk 规则

- `turn_chunk`：一轮“达人消息 + 媒介回复 + 最近 3 条上下文”。
- `episode_chunk`：同一目标下的连续消息，用于场景级召回。
- `template_chunk`：参数化话术，用于高精度模板召回。
- `policy_chunk`：SOP 规则卡，用于流程和风控召回。

## 9. SFT Bucket 归档

- `cold_outreach`：cold_outreach, contact_established
- `brief_delivery`：brief_delivery, quote_collection
- `negotiation`：rights_negotiation, price_negotiation, rebate_negotiation, schedule_lock
- `execution`：cooperation_confirmation, supplier_onboarding, payment_push, execution_followup, revision_coordination, publication_confirmation, data_feedback, repeat_collaboration
- `rebate_recovery`：rebate_recovery

## 10. 人工金标建议

- 第一批先从现有 episode 中筛 50-100 条做金标。
- 覆盖至少 8 类高价值场景：brief、砍价、返点、档期、付款、入库、执行、返点追回。
- 每条金标记录都应保留：`workflow_stage`、`episode_goal`、`objection_type`、`creator_traits`、`source_refs`、`review_notes`。
