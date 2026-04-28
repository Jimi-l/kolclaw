
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional


# ============ Enums ============

class Role(str, Enum):
    AGENCY = "agency"
    CREATOR = "creator"
    SYSTEM = "system"


class Stage(str, Enum):
    OPENING = "opening"
    IDENTITY_INTRO = "identity_intro"
    INTEREST_PROBE = "interest_probe"
    PRICE_INQUIRY = "price_inquiry"
    PRICE_NEGOTIATION = "price_negotiation"
    BRIEF_ALIGNMENT = "brief_alignment"
    SCHEDULE_CONFIRMATION = "schedule_confirmation"
    FOLLOW_UP = "follow_up"
    CLOSING = "closing"
    AFTER_SALES = "after_sales"
    UNKNOWN = "unknown"


class Scene(str, Enum):
    GREETING = "greeting"
    SELF_INTRO = "self_intro"
    ASK_AVAILABILITY = "ask_availability"
    ASK_PRICE = "ask_price"
    EXPLAIN_PRICE = "explain_price"
    BARGAIN = "bargain"
    SEND_BRIEF = "send_brief"
    CONFIRM_SCHEDULE = "confirm_schedule"
    PROMPT_REPLY = "prompt_reply"
    HANDLE_OBJECTION = "handle_objection"
    WRAP_UP = "wrap_up"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class CreatorIntent(str, Enum):
    ASK_ABOUT_COLLABORATION = "ask_about_collaboration"
    ASK_ABOUT_PRICE = "ask_about_price"
    PROVIDE_PRICE = "provide_price"
    DECLINE = "decline"
    HESITATE = "hesitate"
    REQUEST_MATERIALS = "request_materials"
    CONFIRM_SCHEDULE = "confirm_schedule"
    ASK_DETAILS = "ask_details"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class AgencyIntent(str, Enum):
    INTRODUCE_SELF = "introduce_self"
    EXPLAIN_COLLABORATION = "explain_collaboration"
    ASK_INTEREST = "ask_interest"
    INQUIRE_PRICE = "inquire_price"
    EXPLAIN_BUDGET = "explain_budget"
    NEGOTIATE_PRICE = "negotiate_price"
    SEND_BRIEF = "send_brief"
    CONFIRM_SCHEDULE = "confirm_schedule"
    PROMPT_REPLY = "prompt_reply"
    ADDRESS_CONCERN = "address_concern"
    WRAP_UP = "wrap_up"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"


class Tone(str, Enum):
    POLITE = "polite"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    URGENT = "urgent"
    FIRM = "firm"
    SOFT_PUSH = "soft_push"
    NEUTRAL = "neutral"


class Outcome(str, Enum):
    ADVANCED = "advanced"
    STALLED = "stalled"
    REJECTED = "rejected"
    WAITING = "waiting"
    CONVERTED = "converted"
    UNKNOWN = "unknown"


class LabelSource(str, Enum):
    RULE_BASED = "rule_based"
    LLM_ANNOTATED = "llm_annotated"
    HUMAN_REVIEWED = "human_reviewed"
    HUMAN_OVERRIDE = "human_override"


class BusinessRelevance(str, Enum):
    BUSINESS = "business"
    NON_BUSINESS = "non_business"
    UNCERTAIN = "uncertain"


class SampleStatus(str, Enum):
    TRAINABLE = "trainable"
    NEEDS_REVIEW = "needs_review"
    EXCLUDED = "excluded"


class ExclusionReason(str, Enum):
    NON_BUSINESS_SMALL_TALK = "non_business_small_talk"
    NO_VALID_REPLY = "no_valid_reply"
    ONLY_LINK = "only_link"
    ONLY_EMOJI = "only_emoji"
    NON_TEXT_ONLY = "non_text_only"
    SHORT_CONTENT = "short_content"
    LOW_QUALITY = "low_quality"
    OTHER = "other"


# ============ Normalized ============

@dataclass
class NormalizedMessage:
    message_id: str
    conversation_id: str
    seq_num: int
    create_time: int
    formatted_time: str
    role: Role
    role_inference_source: str
    role_confidence: float
    message_type: str
    is_text: bool
    content_masked: str
    sender_id_hash: str
    sender_display_name_masked: str
    platform_message_id_hash: str
    quality_flags: List[str] = field(default_factory=list)
    source_message_ids: List[str] = field(default_factory=list)
    source_seq_nums: List[int] = field(default_factory=list)
    start_time: int = 0
    end_time: int = 0

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "seq_num": self.seq_num,
            "create_time": self.create_time,
            "formatted_time": self.formatted_time,
            "role": self.role.value,
            "role_inference_source": self.role_inference_source,
            "role_confidence": self.role_confidence,
            "message_type": self.message_type,
            "is_text": self.is_text,
            "content_masked": self.content_masked,
            "sender_id_hash": self.sender_id_hash,
            "sender_display_name_masked": self.sender_display_name_masked,
            "platform_message_id_hash": self.platform_message_id_hash,
            "quality_flags": self.quality_flags,
            "source_message_ids": self.source_message_ids,
            "source_seq_nums": self.source_seq_nums,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class NormalizedConversation:
    conversation_id: str
    source_file: str
    conversation_type: str
    contact_display_name_masked: str
    contact_id_hash: str
    message_count_raw: int
    message_count_normalized: int
    started_at: int
    ended_at: int
    weflow_version: str
    exported_at: int
    messages: List[NormalizedMessage] = field(default_factory=list)

    def to_dict(self, include_messages: bool = False) -> dict:
        d = {
            "conversation_id": self.conversation_id,
            "source_file": self.source_file,
            "conversation_type": self.conversation_type,
            "contact_display_name_masked": self.contact_display_name_masked,
            "contact_id_hash": self.contact_id_hash,
            "message_count_raw": self.message_count_raw,
            "message_count_normalized": self.message_count_normalized,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "weflow_version": self.weflow_version,
            "exported_at": self.exported_at,
        }
        if include_messages:
            d["messages"] = [m.to_dict() for m in self.messages]
        return d


# ============ Conversation Turns & Training Samples ============

@dataclass
class ContextMessage:
    message_id: str
    role: str
    content_masked: str
    create_time: int

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content_masked": self.content_masked,
            "create_time": self.create_time,
        }


@dataclass
class ConversationTurn:
    turn_id: str
    conversation_id: str
    creator_message: NormalizedMessage
    agency_reply: NormalizedMessage
    context_messages: List[ContextMessage]
    stage: Stage = Stage.UNKNOWN
    scene: Scene = Scene.UNKNOWN
    creator_intent: CreatorIntent = CreatorIntent.UNKNOWN
    agency_intent: AgencyIntent = AgencyIntent.UNKNOWN
    tone: Tone = Tone.NEUTRAL
    outcome: Outcome = Outcome.UNKNOWN
    label_source: LabelSource = LabelSource.RULE_BASED
    needs_review: bool = False

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "creator_message": self.creator_message.to_dict(),
            "agency_reply": self.agency_reply.to_dict(),
            "context_messages": [cm.to_dict() for cm in self.context_messages],
            "stage": self.stage.value,
            "scene": self.scene.value,
            "creator_intent": self.creator_intent.value,
            "agency_intent": self.agency_intent.value,
            "tone": self.tone.value,
            "outcome": self.outcome.value,
            "label_source": self.label_source.value,
            "needs_review": self.needs_review,
        }


@dataclass
class TrainingSample:
    sample_id: str
    conversation_id: str
    turn_id: str
    stage: Stage
    scene: Scene
    context_messages: List[ContextMessage]
    creator_message: str
    agency_reply: str
    creator_intent: CreatorIntent
    agency_intent: AgencyIntent
    tone: Tone
    outcome: Outcome
    template_candidate: Optional[str] = None
    quality_score: float = 0.5
    needs_review: bool = False
    quality_flags: List[str] = field(default_factory=list)
    business_relevance: BusinessRelevance = BusinessRelevance.UNCERTAIN
    sample_status: SampleStatus = SampleStatus.NEEDS_REVIEW
    exclusion_reason: Optional[ExclusionReason] = None
    source_message_ids: List[str] = field(default_factory=list)
    source_seq_nums: List[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sample_id": self.sample_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "stage": self.stage.value,
            "scene": self.scene.value,
            "context_messages": [cm.to_dict() for cm in self.context_messages],
            "creator_message": self.creator_message,
            "agency_reply": self.agency_reply,
            "creator_intent": self.creator_intent.value,
            "agency_intent": self.agency_intent.value,
            "tone": self.tone.value,
            "outcome": self.outcome.value,
            "template_candidate": self.template_candidate,
            "quality_score": self.quality_score,
            "needs_review": self.needs_review,
            "quality_flags": self.quality_flags,
            "business_relevance": self.business_relevance.value,
            "sample_status": self.sample_status.value,
            "exclusion_reason": self.exclusion_reason.value if self.exclusion_reason else None,
            "source_message_ids": self.source_message_ids,
            "source_seq_nums": self.source_seq_nums,
        }


# ============ Template Candidates ============

@dataclass
class TalkTemplate:
    template_id: str
    template_text: str
    example_reply: str
    stage: Stage
    scene: Scene
    agency_intent: AgencyIntent
    tone: Tone
    count: int
    reusable_score: float
    business_value_score: float
    source_sample_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_text": self.template_text,
            "example_reply": self.example_reply,
            "stage": self.stage.value,
            "scene": self.scene.value,
            "agency_intent": self.agency_intent.value,
            "tone": self.tone.value,
            "count": self.count,
            "reusable_score": self.reusable_score,
            "business_value_score": self.business_value_score,
            "source_sample_ids": self.source_sample_ids,
        }

    def to_csv_row(self) -> List[str]:
        return [
            self.template_id,
            self.template_text.replace("\n", "\\n"),
            self.example_reply.replace("\n", "\\n"),
            self.stage.value,
            self.scene.value,
            self.agency_intent.value,
            self.tone.value,
            str(self.count),
            f"{self.reusable_score:.2f}",
            f"{self.business_value_score:.2f}",
            ",".join(self.source_sample_ids),
        ]

    @classmethod
    def csv_header(cls) -> List[str]:
        return [
            "template_id",
            "template_text",
            "example_reply",
            "stage",
            "scene",
            "agency_intent",
            "tone",
            "count",
            "reusable_score",
            "business_value_score",
            "source_sample_ids",
        ]


# ============ Helpers ============

def short_hash(content: str, length: int = 12) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:length]


def generate_conversation_id(source_file: str, wxid: str, display_name: str) -> str:
    return f"conv_{short_hash(source_file + wxid + display_name)}"


def generate_message_id(conversation_id: str, seq_num: int) -> str:
    return f"{conversation_id}_msg_{seq_num:04d}"


def generate_turn_id(conversation_id: str, turn_idx: int) -> str:
    return f"{conversation_id}_turn_{turn_idx:04d}"


def generate_sample_id(conversation_id: str, sample_idx: int) -> str:
    return f"{conversation_id}_sample_{sample_idx:04d}"


def generate_template_id(template_text: str) -> str:
    return f"tpl_{short_hash(template_text)}"
