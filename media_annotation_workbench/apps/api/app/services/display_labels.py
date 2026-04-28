from __future__ import annotations

from typing import Any


ASSET_TYPE_LABELS: dict[str, str] = {
    "conversation_messages": "标准化消息",
    "brief_cards": "Brief 知识卡",
    "negotiation_episodes": "谈判片段",
    "talk_templates": "话术模板",
    "workflow_playbook": "履约 SOP",
    "retrieval_chunks": "检索切片",
    "gold_episode_review_queue": "人工审核队列",
    "tag_dictionary": "标签字典",
    "annotation_guideline": "标注规范",
    "asset_field_guide": "字段说明",
}

USER_ROLE_LABELS: dict[str, str] = {
    "admin": "管理员",
    "annotator": "业务标注员",
    "viewer": "只读访客",
}

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending": "待审核",
    "in_progress": "审核中",
    "submitted": "待管理员审核",
    "approved": "已通过",
    "returned": "已退回",
}

ROLE_LABELS: dict[str, str] = {
    "agency": "媒介",
    "creator": "达人",
}

PRIORITY_LABELS: dict[str, str] = {
    "high": "高优先级",
    "medium": "中优先级",
    "low": "低优先级",
}

WORKFLOW_STAGE_SHORT_LABELS: dict[str, str] = {
    "cold_outreach": "冷启动建联",
    "contact_established": "建立联系",
    "brief_delivery": "brief下达",
    "quote_collection": "询价收集",
    "rights_negotiation": "权益协商",
    "price_negotiation": "砍价",
    "rebate_negotiation": "返点谈判",
    "schedule_lock": "锁档推进",
    "cooperation_confirmation": "合作确认",
    "supplier_onboarding": "供应商入库",
    "payment_push": "付款推进",
    "execution_followup": "执行跟进",
    "revision_coordination": "修改协调",
    "publication_confirmation": "发布确认",
    "data_feedback": "数据回收",
    "rebate_recovery": "返点追回",
    "repeat_collaboration": "再次合作",
}

WORKFLOW_STAGE_DESCRIPTIONS: dict[str, str] = {
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

EPISODE_GOAL_LABELS: dict[str, str] = {
    "get_reply": "拿到回复",
    "collect_quote": "收集报价",
    "raise_rebate": "提升返点",
    "cut_price": "争取降价",
    "secure_schedule": "确认档期",
    "confirm_rights": "确认权益",
    "collect_docs": "收集资料",
    "lock_execution": "锁定执行",
    "push_payment": "推动付款",
    "confirm_publish": "确认发布",
    "collect_data": "回收数据",
    "recover_rebate": "追回返点",
}

OBJECTION_TYPE_LABELS: dict[str, str] = {
    "price_too_high": "报价过高",
    "rebate_below_target": "返点未达标",
    "no_free_distribution": "免费分发不足",
    "rights_limited": "权益受限",
    "schedule_risk": "档期风险",
    "payment_rule_rigid": "付款规则僵硬",
    "document_missing": "资料缺失",
    "cannot_guarantee_metrics": "无法保量",
    "no_secondary_creation": "不接受二创",
    "platform_rule_rigid": "平台规则强约束",
    "none": "无明显阻力",
}

OUTCOME_LABELS: dict[str, str] = {
    "advanced": "已推进",
    "waiting": "等待中",
    "partial_progress": "部分推进",
    "confirmed": "已确认",
    "blocked": "已受阻",
}

KNOWLEDGE_BASE_LABELS: dict[str, str] = {
    "brief_framework": "达人 brief 框架",
    "negotiation_scene": "砍价/返点场景",
    "talk_library": "话术知识库",
    "fulfillment_sop": "履约 SOP",
}

REVIEW_EVENT_LABELS: dict[str, str] = {
    "imported": "导入生成",
    "claimed": "已领取",
    "draft_saved": "已保存草稿",
    "submitted": "已提交审核",
    "approved": "审核通过",
    "returned": "审核退回",
}


def label_for(mapping: dict[str, str], key: str | None, fallback: str | None = None) -> str | None:
    if key is None:
        return fallback
    return mapping.get(key, fallback or key)


def make_option_items(mapping: dict[str, str], descriptions: dict[str, str] | None = None) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for key, label in mapping.items():
        option = {"key": key, "label": label}
        if descriptions and descriptions.get(key):
            option["description"] = descriptions[key]
        options.append(option)
    return options
