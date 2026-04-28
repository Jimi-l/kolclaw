
from __future__ import annotations

import re
from typing import List

from .schemas import (
    ContextMessage,
    ConversationTurn,
    CreatorIntent,
    AgencyIntent,
    LabelSource,
    NormalizedConversation,
    NormalizedMessage,
    Outcome,
    Role,
    Scene,
    Stage,
    Tone,
    short_hash,
    generate_conversation_id,
    generate_message_id,
)


URL_PATTERN = re.compile(r"https?://[^\s]+")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
WECHAT_ID_PATTERN = re.compile(r"wxid_[a-zA-Z0-9_-]+")
LONG_NUMBER_PATTERN = re.compile(r"\d{8,}")


def mask_pii(text: str | None) -> str:
    if text is None:
        return ""
    text = str(text)
    text = URL_PATTERN.sub("[URL]", text)
    text = EMAIL_PATTERN.sub("[EMAIL]", text)
    text = PHONE_PATTERN.sub("[PHONE]", text)
    text = WECHAT_ID_PATTERN.sub("[WECHAT_ID]", text)
    text = LONG_NUMBER_PATTERN.sub("[NUMBER]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mask_display_name(name: str | None) -> str:
    if name is None:
        return ""
    name = str(name)
    if not name:
        return ""
    if len(name) <= 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


class WeFlowNormalizer:
    def __init__(self):
        pass

    def normalize_conversation(
        self,
        raw_data: dict,
        source_file: str,
    ) -> tuple[NormalizedConversation, list[str]]:
        warnings: list[str] = []

        weflow_meta = raw_data.get("weflow", {})
        session = raw_data.get("session", {})
        raw_messages = raw_data.get("messages", [])

        wxid = session.get("wxid", "")
        display_name = session.get("displayName", "")
        conversation_id = generate_conversation_id(source_file, wxid, display_name)

        message_count_raw = len(raw_messages)
        started_at = 0
        ended_at = 0
        if raw_messages:
            started_at = raw_messages[0].get("createTime", 0)
            ended_at = raw_messages[-1].get("createTime", 0)

        normalized_messages: list[NormalizedMessage] = []
        for idx, raw_msg in enumerate(raw_messages):
            msg, msg_warnings = self.normalize_message(
                raw_msg, conversation_id, idx + 1
            )
            normalized_messages.append(msg)
            warnings.extend(msg_warnings)

        conversation = NormalizedConversation(
            conversation_id=conversation_id,
            source_file=source_file,
            conversation_type=session.get("type", ""),
            contact_display_name_masked=mask_display_name(display_name),
            contact_id_hash=short_hash(wxid),
            message_count_raw=message_count_raw,
            message_count_normalized=len(normalized_messages),
            started_at=started_at,
            ended_at=ended_at,
            weflow_version=weflow_meta.get("version", ""),
            exported_at=weflow_meta.get("exportedAt", 0),
            messages=normalized_messages,
        )

        return conversation, warnings

    def normalize_message(
        self,
        raw_msg: dict,
        conversation_id: str,
        seq_num: int,
    ) -> tuple[NormalizedMessage, list[str]]:
        warnings: list[str] = []

        message_id = generate_message_id(conversation_id, seq_num)

        create_time = raw_msg.get("createTime", 0)
        formatted_time = raw_msg.get("formattedTime", "")
        msg_type = raw_msg.get("type", "")
        content = raw_msg.get("content")
        is_send = raw_msg.get("isSend", 0)
        sender_username = raw_msg.get("senderUsername", "")
        sender_display_name = raw_msg.get("senderDisplayName", "")
        platform_message_id = raw_msg.get("platformMessageId", "")

        is_text = msg_type == "文本消息" and isinstance(content, str) and content is not None

        if is_send == 1:
            role = Role.AGENCY
        elif is_send == 0:
            role = Role.CREATOR
        else:
            role = Role.SYSTEM
            warnings.append(f"Message {seq_num}: unexpected isSend value {is_send}")

        content_masked = mask_pii(content)
        if not is_text and content is None:
            content_masked = f"[NON_TEXT:{msg_type}]"

        quality_flags: list[str] = []
        if not is_text:
            quality_flags.append("non_text")
        if not content_masked:
            quality_flags.append("empty_content")

        normalized_msg = NormalizedMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            seq_num=seq_num,
            create_time=create_time,
            formatted_time=formatted_time,
            role=role,
            role_inference_source="is_send",
            role_confidence=1.0 if role != Role.SYSTEM else 0.5,
            message_type=msg_type,
            is_text=is_text,
            content_masked=content_masked,
            sender_id_hash=short_hash(sender_username),
            sender_display_name_masked=mask_display_name(sender_display_name),
            platform_message_id_hash=short_hash(platform_message_id),
            quality_flags=quality_flags,
            source_message_ids=[message_id],
            source_seq_nums=[seq_num],
            start_time=create_time,
            end_time=create_time,
        )

        return normalized_msg, warnings


STRONG_BUSINESS_KEYWORDS = [
    "达人", "接广", "商单", "合作", "报价", "报价单", "预算",
    "档期", "排期", "brief", "Brief", "推广", "投放", "佣金",
    "坑位费", "结款", "数据反馈", "效果数据", "投放数据",
    "寄样", "植入", "星图", "蒲公英", "小红书", "抖音",
]

WEAK_BUSINESS_KEYWORDS = [
    "品牌", "产品", "视频", "图文", "直播", "内容", "数据",
]

AMOUNT_PATTERN = re.compile(r"([¥￥]\s*)?\d+(?:\.\d+)?\s*(元|块|万|k|K)?")


KEYWORDS_STAGE = {
    Stage.OPENING: ["你好", "您好", "在吗", "嗨", "hi"],
    Stage.IDENTITY_INTRO: ["我是", "我们是", "公司", "介绍一下"],
    Stage.INTEREST_PROBE: ["接吗", "合作", "档期", "有时间吗"],
    Stage.PRICE_INQUIRY: ["多少钱", "报价", "费用", "价格"],
    Stage.PRICE_NEGOTIATION: ["便宜", "优惠", "折扣", "砍价", "贵了", "预算"],
    Stage.BRIEF_ALIGNMENT: ["brief", "Brief", "需求", "产品", "资料"],
    Stage.SCHEDULE_CONFIRMATION: ["时间", "排期", "日期", "号", "可以吗"],
    Stage.FOLLOW_UP: ["方便回一下", "看到消息吗", "等你回复", "催"],
    Stage.CLOSING: ["谢谢", "好的", "没问题", "那就", "定了"],
    Stage.AFTER_SALES: ["数据反馈", "结款", "效果数据", "投放数据"],
}

KEYWORDS_SCENE = {
    Scene.GREETING: ["你好", "您好", "在吗", "嗨"],
    Scene.SELF_INTRO: ["我是", "我们是", "公司"],
    Scene.ASK_AVAILABILITY: ["接吗", "合作", "档期", "有时间"],
    Scene.ASK_PRICE: ["多少钱", "报价", "费用", "价格"],
    Scene.EXPLAIN_PRICE: ["我们的报价", "费用是", "价格是"],
    Scene.BARGAIN: ["便宜", "优惠", "折扣", "贵了", "预算"],
    Scene.SEND_BRIEF: ["brief", "Brief", "需求", "产品", "资料"],
    Scene.CONFIRM_SCHEDULE: ["时间", "排期", "日期", "号", "可以吗"],
    Scene.PROMPT_REPLY: ["方便回一下", "看到消息吗", "等你回复"],
    Scene.WRAP_UP: ["谢谢", "好的", "没问题", "定了"],
    Scene.SMALL_TALK: ["哈哈", "嗯嗯", "对的", "是的", "好的"],
}


def is_business_relevant(text: str) -> bool:
    text_lower = text.lower()
    for kw in STRONG_BUSINESS_KEYWORDS:
        if kw.lower() in text_lower:
            return True

    weak_hits = 0
    for kw in WEAK_BUSINESS_KEYWORDS:
        if kw in text:
            weak_hits += 1

    has_amount = any(ch in text for ch in ["¥", "￥", "元", "块", "万"]) and bool(AMOUNT_PATTERN.search(text))
    return weak_hits >= 2 or (weak_hits >= 1 and has_amount)


def weak_label_stage(text: str) -> Stage:
    text_lower = text.lower()
    weighted_rules = [
        (Stage.BRIEF_ALIGNMENT, 100),
        (Stage.PRICE_NEGOTIATION, 90),
        (Stage.PRICE_INQUIRY, 85),
        (Stage.SCHEDULE_CONFIRMATION, 80),
        (Stage.INTEREST_PROBE, 70),
        (Stage.IDENTITY_INTRO, 60),
        (Stage.AFTER_SALES, 50),
        (Stage.FOLLOW_UP, 45),
        (Stage.CLOSING, 30),
        (Stage.OPENING, 10),
    ]
    best_stage = Stage.UNKNOWN
    best_score = 0
    for stage, score in weighted_rules:
        for kw in KEYWORDS_STAGE.get(stage, []):
            if kw.lower() in text_lower and score > best_score:
                best_stage = stage
                best_score = score
    if best_stage != Stage.UNKNOWN:
        return best_stage
    return Stage.UNKNOWN


def weak_label_scene(text: str) -> Scene:
    text_lower = text.lower()
    weighted_rules = [
        (Scene.SEND_BRIEF, 100),
        (Scene.BARGAIN, 90),
        (Scene.ASK_PRICE, 85),
        (Scene.EXPLAIN_PRICE, 82),
        (Scene.CONFIRM_SCHEDULE, 80),
        (Scene.ASK_AVAILABILITY, 70),
        (Scene.SELF_INTRO, 60),
        (Scene.PROMPT_REPLY, 50),
        (Scene.WRAP_UP, 30),
        (Scene.SMALL_TALK, 20),
        (Scene.GREETING, 10),
    ]
    best_scene = Scene.UNKNOWN
    best_score = 0
    for scene, score in weighted_rules:
        for kw in KEYWORDS_SCENE.get(scene, []):
            if kw.lower() in text_lower and score > best_score:
                best_scene = scene
                best_score = score
    if best_scene != Scene.UNKNOWN:
        return best_scene
    return Scene.UNKNOWN


def weak_label_creator_intent(text: str) -> CreatorIntent:
    text = text.lower()
    if any(kw in text for kw in ["多少钱", "报价", "费用"]):
        return CreatorIntent.ASK_ABOUT_PRICE
    if any(kw in text for kw in ["接吗", "合作", "档期"]):
        return CreatorIntent.ASK_ABOUT_COLLABORATION
    if any(kw in text for kw in ["不接", "没时间", "算了"]):
        return CreatorIntent.DECLINE
    if any(kw in text for kw in ["我考虑", "看看", "再说"]):
        return CreatorIntent.HESITATE
    if any(kw in text for kw in ["发一下", "给我", "看看资料"]):
        return CreatorIntent.REQUEST_MATERIALS
    if any(kw in text for kw in ["时间", "排期", "日期"]):
        return CreatorIntent.CONFIRM_SCHEDULE
    if any(kw in text for kw in ["详细", "具体", "怎么"]):
        return CreatorIntent.ASK_DETAILS
    return CreatorIntent.UNKNOWN


def weak_label_agency_intent(text: str) -> AgencyIntent:
    text = text.lower()
    if any(kw in text for kw in ["我是", "我们是", "公司"]):
        return AgencyIntent.INTRODUCE_SELF
    if any(kw in text for kw in ["合作", "我们这边", "有个"]):
        return AgencyIntent.EXPLAIN_COLLABORATION
    if any(kw in text for kw in ["接吗", "有档期", "有时间"]):
        return AgencyIntent.ASK_INTEREST
    if any(kw in text for kw in ["报价", "费用", "多少钱"]):
        return AgencyIntent.INQUIRE_PRICE
    if any(kw in text for kw in ["预算", "我们这边"]):
        return AgencyIntent.EXPLAIN_BUDGET
    if any(kw in text for kw in ["便宜", "优惠", "折扣"]):
        return AgencyIntent.NEGOTIATE_PRICE
    if any(kw in text for kw in ["brief", "Brief", "需求", "产品"]):
        return AgencyIntent.SEND_BRIEF
    if any(kw in text for kw in ["时间", "排期", "日期", "可以吗"]):
        return AgencyIntent.CONFIRM_SCHEDULE
    if any(kw in text for kw in ["方便回", "看到消息", "等你"]):
        return AgencyIntent.PROMPT_REPLY
    if any(kw in text for kw in ["没问题", "放心", "理解"]):
        return AgencyIntent.ADDRESS_CONCERN
    if any(kw in text for kw in ["谢谢", "好的", "那就"]):
        return AgencyIntent.WRAP_UP
    return AgencyIntent.UNKNOWN


def weak_label_tone(text: str) -> Tone:
    text = text.lower()
    if any(kw in text for kw in ["请", "麻烦", "谢谢", "您好"]):
        return Tone.POLITE
    if any(kw in text for kw in ["哈", "呀", "～", "啦"]):
        return Tone.FRIENDLY
    if any(kw in text for kw in ["尽快", "赶紧", "麻烦尽快", "很急"]):
        return Tone.URGENT
    return Tone.NEUTRAL


def weak_label_outcome(text: str) -> Outcome:
    return Outcome.UNKNOWN


class WeakLabeler:
    def label_turn(self, turn: ConversationTurn) -> ConversationTurn:
        creator_text = turn.creator_message.content_masked
        agency_text = turn.agency_reply.content_masked
        combined_text = creator_text + " " + agency_text

        if is_business_relevant(combined_text):
            turn.stage = weak_label_stage(combined_text)
            turn.scene = weak_label_scene(combined_text)
            turn.creator_intent = weak_label_creator_intent(creator_text)
            turn.agency_intent = weak_label_agency_intent(agency_text)
        else:
            turn.stage = Stage.UNKNOWN
            turn.scene = Scene.SMALL_TALK
            turn.creator_intent = CreatorIntent.SMALL_TALK
            turn.agency_intent = AgencyIntent.SMALL_TALK

        turn.tone = weak_label_tone(agency_text)
        turn.outcome = weak_label_outcome(agency_text)
        turn.label_source = LabelSource.RULE_BASED

        if turn.stage == Stage.UNKNOWN and turn.scene != Scene.SMALL_TALK:
            turn.needs_review = True

        return turn
