from __future__ import annotations


PLATFORM = "wechat"
CHANNEL_TYPE = "private_chat"
SCHEMA_VERSION = "v1"


WORKFLOW_STAGES: dict[str, str] = {
    "cold_outreach": "首次冷启动触达达人，目标是拿到回复或建立联系。",
    "contact_established": "已建立基础联系，如通过好友验证、确认沟通窗口。",
    "brief_delivery": "媒介向达人发送合作背景、需求和待确认项。",
    "quote_collection": "达人返回报价、返点、档期、权益、合作须知。",
    "rights_negotiation": "围绕授权、分发、二创、置顶、保留时长等权益协商。",
    "price_negotiation": "围绕刊例价、水下价、打包价、改价进行谈判。",
    "rebate_negotiation": "围绕返点目标、返点补差、服务费压力进行谈判。",
    "schedule_lock": "围绕档期、锁档、定金、发布时间风险进行推进。",
    "cooperation_confirmation": "双方确认合作意向、合作成立或锁定合作。",
    "supplier_onboarding": "收集入库、营业执照、收款、发票、账号等资料。",
    "payment_push": "催款、请款、下单、尾款、定金等支付推进。",
    "execution_followup": "拉执行群、推进制作、脚本、交付、发布准备。",
    "revision_coordination": "围绕修改次数、重拍、脚本调整、额外要求沟通。",
    "publication_confirmation": "确认发布动作、发布时间、平台挂载和上线结果。",
    "data_feedback": "围绕播放、互动、保量、投放维护、数据回传沟通。",
    "rebate_recovery": "围绕返点回收、返点打款、返点材料和打款凭证推进。",
    "repeat_collaboration": "复购或再次合作的延展沟通。",
}


EPISODE_GOALS: dict[str, str] = {
    "get_reply": "拿到达人回复或确认后续沟通入口。",
    "collect_quote": "拿到完整报价、返点、权益和档期。",
    "raise_rebate": "把返点提升到目标线附近。",
    "cut_price": "争取降价或用权益换价。",
    "secure_schedule": "确保达人能留档并满足发布时间。",
    "confirm_rights": "确认分发、授权、二创、置顶、保留时长等权益。",
    "collect_docs": "收集入库、开票、收款、主体证明等资料。",
    "lock_execution": "确认合作、拉执行、推进制作与交付。",
    "push_payment": "推动定金、尾款或正式下单完成。",
    "confirm_publish": "确认内容已发布或具备发布条件。",
    "collect_data": "催数据回传、维护数据或解释数据表现。",
    "recover_rebate": "追回返点并拿到打款凭据。",
}


OBJECTION_TYPES: dict[str, str] = {
    "price_too_high": "客户或媒介认为报价偏高，需要砍价。",
    "rebate_below_target": "当前返点低于媒介目标，影响利润或服务费。",
    "no_free_distribution": "免费分发平台不满足要求。",
    "rights_limited": "授权、投流、保留期等权益受限。",
    "schedule_risk": "档期、制作周期、留档方式导致发布时间风险。",
    "payment_rule_rigid": "付款、请款、下单规则僵硬，阻塞合作推进。",
    "document_missing": "营业执照、入库、开票或收款资料不全。",
    "cannot_guarantee_metrics": "达人无法保量、保赞或解释数据。",
    "no_secondary_creation": "达人不接受二创、二剪等再创作要求。",
    "platform_rule_rigid": "平台或公司规则强约束，难以灵活变通。",
    "none": "该 episode 不存在明显 objection。",
}


CREATOR_TRAIT_DICTIONARY: dict[str, dict[str, str]] = {
    "order_saturation": {
        "high": "达人不缺单或档期紧张，议价空间偏小。",
        "medium": "达人有一定单量压力，但仍可沟通。",
        "low": "达人相对缺单，通常更愿意换价或换权益。",
        "unknown": "没有足够证据判断达人是否缺单。",
    },
    "flexibility_level": {
        "rigid": "规则边界强，几乎不愿改价或改权益。",
        "negotiable": "可在局部条件上协商调整。",
        "highly_flexible": "愿意大幅让利或快速给出替代方案。",
        "unknown": "无法判断灵活度。",
    },
    "interaction_style": {
        "friendly": "语气亲和，愿意顺着媒介推进。",
        "professional": "偏流程化、规范化、信息完整。",
        "direct": "表达简短直接，少寒暄。",
        "cautious": "多次确认细节，推进偏谨慎。",
        "strong_boundary": "强边界，不轻易让步或反复强调规则。",
        "unknown": "缺乏足够互动判断。",
    },
    "decision_speed": {
        "fast": "回复快、确认快、推进快。",
        "normal": "常规响应速度。",
        "slow": "明显存在等待、拖延或多轮确认。",
        "unknown": "无法判断。",
    },
}


COMMERCIAL_STATE_DICTIONARY: dict[str, str] = {
    "listed_price": "达人当前提供的公开或口头报价。",
    "target_price": "媒介希望落到的成交价格或改价目标。",
    "current_rebate_rate": "达人当前提供的返点比例。",
    "target_rebate_rate": "媒介希望争取到的返点比例。",
    "rebate_target_status": "当前返点是否达到目标线。",
    "agency_margin_pressure": "媒介利润压力程度。",
    "rights_gap_status": "权益是否已满足客户要求。",
    "payment_blocker_type": "当前付款推进的主要阻塞类型。",
}


CHUNK_TYPES: dict[str, str] = {
    "turn_chunk": "达人消息 + 媒介回复 + 最近 3 条上下文。",
    "episode_chunk": "围绕一个业务目标的连续消息切片。",
    "template_chunk": "参数化后的媒介话术模板切片。",
    "policy_chunk": "SOP / 规则卡切片。",
}


SFT_BUCKETS: dict[str, list[str]] = {
    "cold_outreach": ["cold_outreach", "contact_established"],
    "brief_delivery": ["brief_delivery", "quote_collection"],
    "negotiation": ["rights_negotiation", "price_negotiation", "rebate_negotiation", "schedule_lock"],
    "execution": ["cooperation_confirmation", "supplier_onboarding", "payment_push", "execution_followup", "revision_coordination", "publication_confirmation", "data_feedback", "repeat_collaboration"],
    "rebate_recovery": ["rebate_recovery"],
}


KNOWLEDGE_BASES: dict[str, str] = {
    "brief_framework": "达人 brief 沟通框架知识库",
    "negotiation_scene": "砍价 / 返点场景知识库",
    "talk_library": "话术知识库",
    "fulfillment_sop": "履约 SOP 知识库",
}


COMMON_NOISE_MESSAGES = {
    "好的",
    "收到",
    "好滴",
    "好嘞",
    "ok",
    "okk",
    "嗯嗯",
    "好",
    "来了",
    "在",
}


MANUAL_PLAYBOOK_STEPS = [
    {
        "step_id": "playbook_001",
        "knowledge_base": "talk_library",
        "workflow_stage": "cold_outreach",
        "trigger_condition": "已拿到达人账号，但尚未建立有效沟通。",
        "required_inputs": ["品牌名", "产品方向", "合作平台", "一句话合作诉求"],
        "recommended_action": "先用轻量自报家门 + 合作意向的开场话术触达，目标是拿到有效回复。",
        "fallback_action": "若 24 小时未回复，换更短的提醒式 follow-up，并补充一句对达人内容方向的认可。",
        "exit_condition": "达人回复，或明确无回复后进入人工切换渠道。",
    },
    {
        "step_id": "playbook_002",
        "knowledge_base": "talk_library",
        "workflow_stage": "contact_established",
        "trigger_condition": "达人已通过好友验证或给出可继续沟通的窗口。",
        "required_inputs": ["合作背景", "平台", "基础项目名称"],
        "recommended_action": "快速说明来意，不在此阶段堆过多执行细节，先确认对方可看需求。",
        "fallback_action": "若对方只回了礼貌性消息，追加一句“辛苦看下需求是否合适”。",
        "exit_condition": "达人明确愿意看需求，或要求先发 brief。",
    },
    {
        "step_id": "playbook_003",
        "knowledge_base": "brief_framework",
        "workflow_stage": "brief_delivery",
        "trigger_condition": "达人愿意了解合作。",
        "required_inputs": ["品牌", "产品", "合作平台", "内容方向", "档期", "待确认权益项"],
        "recommended_action": "按固定问询框架发送 brief，优先一次性把报价、返点、分发、授权、档期、保量、制作周期问全。",
        "fallback_action": "若达人不接受长消息，拆成“需求概览 + 待确认清单”两段发送。",
        "exit_condition": "达人开始回复 checklist 或返回报价单。",
    },
    {
        "step_id": "playbook_004",
        "knowledge_base": "brief_framework",
        "workflow_stage": "quote_collection",
        "trigger_condition": "达人开始反馈报价与合作条件。",
        "required_inputs": ["完整问询框架", "客户硬性权益底线"],
        "recommended_action": "优先补齐缺口字段，不急着砍价，先确认是否具备成单基础。",
        "fallback_action": "如果达人只回部分条件，定向追问缺失项，不要把所有问题重复发一遍。",
        "exit_condition": "形成完整报价 / 权益 / 档期信息卡。",
    },
    {
        "step_id": "playbook_005",
        "knowledge_base": "negotiation_scene",
        "workflow_stage": "rights_negotiation",
        "trigger_condition": "授权、二创、分发、投流、保留时长不满足客户要求。",
        "required_inputs": ["客户权益底线", "达人已答复权益", "可替换方案"],
        "recommended_action": "明确指出缺口项，并用“换平台 / 换时长 / 换挂载方式”争取替代解法。",
        "fallback_action": "若达人规则刚性强，则快速判断该缺口是否可由客户侧放宽，而不是长拉扯。",
        "exit_condition": "权益满足、找到替代方案，或确认无解。",
    },
    {
        "step_id": "playbook_006",
        "knowledge_base": "negotiation_scene",
        "workflow_stage": "price_negotiation",
        "trigger_condition": "客户反馈报价偏高或核价不过。",
        "required_inputs": ["达人报价", "目标价格", "客户预算压力", "可交换权益"],
        "recommended_action": "先说明预算压力来源，再尝试用改价、减权益、降分发或延后平台换价。",
        "fallback_action": "若达人拒绝直接降价，则切到“换权益 / 换交付范围 / 换平台组合”的谈法。",
        "exit_condition": "价格降到目标附近，或确认无法再降。",
    },
    {
        "step_id": "playbook_007",
        "knowledge_base": "negotiation_scene",
        "workflow_stage": "rebate_negotiation",
        "trigger_condition": "返点低于目标线，媒介利润不足。",
        "required_inputs": ["当前返点", "目标返点", "利润压力", "是否已有合作基础"],
        "recommended_action": "用核价压力和服务费压力解释诉求，避免直接空口要返点。",
        "fallback_action": "若达人边界强，改问“最高能给到多少”并同步考虑价格结构重组。",
        "exit_condition": "返点满足目标，或拿到明确的返点上限。",
    },
    {
        "step_id": "playbook_008",
        "knowledge_base": "negotiation_scene",
        "workflow_stage": "schedule_lock",
        "trigger_condition": "客户卡发布时间，达人档期存在竞争或风险。",
        "required_inputs": ["目标发布日期", "达人档期", "付款节奏", "制作周期"],
        "recommended_action": "先确认留档规则和制作周期，再判断是走锁档、定金还是邮件确认。",
        "fallback_action": "若对方必须以下单或定金留档，快速转到付款推进，不要继续空口锁档。",
        "exit_condition": "档期被锁定，或确认当前规则下无法保档。",
    },
    {
        "step_id": "playbook_009",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "cooperation_confirmation",
        "trigger_condition": "价格、返点、权益和档期已基本达成。",
        "required_inputs": ["成交口径", "达人代号", "关键权益摘要"],
        "recommended_action": "用文字再次确认合作要点，方便达人商单报备与内部流转。",
        "fallback_action": "若达人仍模糊，按“达人 / 档期 / 价格 / 权益 / 平台”再发一次总结卡。",
        "exit_condition": "双方确认合作成立并进入资料收集或执行阶段。",
    },
    {
        "step_id": "playbook_010",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "supplier_onboarding",
        "trigger_condition": "合作成立，需要走入库或收款流程。",
        "required_inputs": ["入库模板", "对公 / 对私流程", "主体要求"],
        "recommended_action": "按主体类型发送资料模板，一次性说明营业执照、开票、开户地址、身份证等要求。",
        "fallback_action": "若达人对流程有疑虑，解释用途和复用价值，避免让对方误以为是额外风控。",
        "exit_condition": "入库材料补齐或已确认缺失项和补交时间。",
    },
    {
        "step_id": "playbook_011",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "payment_push",
        "trigger_condition": "定金、尾款或正式下单未完成，影响锁档或制作。",
        "required_inputs": ["付款节点", "达人规则", "公司请款节奏", "阻塞原因"],
        "recommended_action": "把付款规则和发布时间风险说清楚，推动双方接受同一个时间预期。",
        "fallback_action": "若内部请款节奏固定，则尝试争取达人先制作、先锁档或接受定金单。",
        "exit_condition": "达人确认可接受付款安排，或付款已完成。",
    },
    {
        "step_id": "playbook_012",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "execution_followup",
        "trigger_condition": "合作进入执行，需要拉群、推进脚本或确认发票。",
        "required_inputs": ["执行群信息", "脚本要求", "交付节点"],
        "recommended_action": "把执行动作拆成群拉起、制作推进、交付确认三个小节点推进。",
        "fallback_action": "若达人仍卡在付款或资料流程，先把阻塞点闭环再拉执行。",
        "exit_condition": "执行群建立，制作开始或交付节奏已锁定。",
    },
    {
        "step_id": "playbook_013",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "revision_coordination",
        "trigger_condition": "脚本、贴片、画面、权益挂载需要修改。",
        "required_inputs": ["修改意见", "可改范围", "达人限制"],
        "recommended_action": "先确认问题属于客户要求不符还是达人制作边界，再决定是重拍、贴片还是局部调整。",
        "fallback_action": "若达人明确不重拍，优先争取贴片或脚本口播层面补救。",
        "exit_condition": "修改方案达成一致并可继续推进。",
    },
    {
        "step_id": "playbook_014",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "publication_confirmation",
        "trigger_condition": "内容接近上线或已经发布。",
        "required_inputs": ["发布时间", "平台", "挂载要求", "48h/72h 不更新要求"],
        "recommended_action": "上线前再次确认发布时间、挂载方式、评论区互动和不更新窗口。",
        "fallback_action": "若达人临时有排期变化，先保平台发布，再判断分发和置顶是否后补。",
        "exit_condition": "内容已上线且权益无明显缺漏。",
    },
    {
        "step_id": "playbook_015",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "data_feedback",
        "trigger_condition": "项目发布后需要跟踪播放、互动、保量或维护数据。",
        "required_inputs": ["历史承诺值", "当前数据表现", "维护预算"],
        "recommended_action": "优先对齐承诺与现实差距，再决定是补投、解释还是申请达人共担。",
        "fallback_action": "若达人已自行维护过数据，改谈共同承担和后返方式。",
        "exit_condition": "拿到数据回传、维护方案或不维护的明确结论。",
    },
    {
        "step_id": "playbook_016",
        "knowledge_base": "fulfillment_sop",
        "workflow_stage": "rebate_recovery",
        "trigger_condition": "项目发布或结算后进入返点回收周期。",
        "required_inputs": ["返点约定", "结算节点", "收款方式", "打款凭证要求"],
        "recommended_action": "先提醒返点节点，再在对方正面确认后发送收款渠道、开票或打款信息。",
        "fallback_action": "若对方拖延，补发合作确认依据和返点口径，必要时切人工升级。",
        "exit_condition": "返点到账或对方给出明确打款时间。",
    },
    {
        "step_id": "playbook_017",
        "knowledge_base": "talk_library",
        "workflow_stage": "repeat_collaboration",
        "trigger_condition": "项目顺利推进后存在复购可能。",
        "required_inputs": ["本次合作结果", "达人边界", "下次可复用条件"],
        "recommended_action": "沉淀达人可复用的价格、权益和流程偏好，为下一单直接复用。",
        "fallback_action": "若本次推进中有强边界问题，也要把风险写入达人标签。",
        "exit_condition": "形成可复用的达人合作画像。",
    },
]


MANUAL_TALK_TEMPLATES = [
    {
        "template_id": "manual_tpl_001",
        "knowledge_base": "talk_library",
        "scenario_key": "cold_outreach.get_reply.general",
        "workflow_stage": "cold_outreach",
        "template_text": "老师你好，我这边是[BRAND]项目合作，想和您沟通下[PLATFORM]内容合作，方便看下需求吗？",
        "slots": ["BRAND", "PLATFORM"],
        "applicable_conditions": ["适用于首次私信触达", "已有达人账号但尚未建立有效沟通"],
        "risk_notes": ["不要首条消息堆过长 brief", "先以建立回复为目标"],
        "source_episode_ids": [],
        "source_message_ids": [],
        "origin": "manual_seed",
    },
    {
        "template_id": "manual_tpl_002",
        "knowledge_base": "talk_library",
        "scenario_key": "cold_outreach.get_reply.followup",
        "workflow_stage": "cold_outreach",
        "template_text": "老师辛苦看看上条消息，如果您这边近期能接[PLATFORM]合作，我这边再把具体 brief 发您。",
        "slots": ["PLATFORM"],
        "applicable_conditions": ["首次触达后 24 小时未回复", "需要温和 follow-up"],
        "risk_notes": ["避免高频催促", "不建议连续多次使用"],
        "source_episode_ids": [],
        "source_message_ids": [],
        "origin": "manual_seed",
    },
    {
        "template_id": "manual_tpl_003",
        "knowledge_base": "talk_library",
        "scenario_key": "rebate_recovery.recover_rebate.first_notice",
        "workflow_stage": "rebate_recovery",
        "template_text": "老师好，这边同步下[PROJECT]的返点回收节点已到，辛苦帮我看下这边预计什么时候方便安排返点打款呀？",
        "slots": ["PROJECT"],
        "applicable_conditions": ["项目已到返点回收节点", "需要第一轮温和提醒"],
        "risk_notes": ["先确认节点，不要第一句就压迫式催款"],
        "source_episode_ids": [],
        "source_message_ids": [],
        "origin": "manual_seed",
    },
    {
        "template_id": "manual_tpl_004",
        "knowledge_base": "talk_library",
        "scenario_key": "rebate_recovery.recover_rebate.payment_details",
        "workflow_stage": "rebate_recovery",
        "template_text": "好的老师，那我把这边的收款信息同步您，辛苦打款后把凭证也回传我下，方便我这边核销流程。",
        "slots": [],
        "applicable_conditions": ["对方正面确认会返点", "需要补收款信息和凭证"],
        "risk_notes": ["必须在对方确认返点口径后再发收款信息"],
        "source_episode_ids": [],
        "source_message_ids": [],
        "origin": "manual_seed",
    },
]
