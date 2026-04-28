from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CreatorTraitEvidence:
    trait_name: str
    value: str
    confidence: float
    evidence_message_ids: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationMessage:
    message_id: str
    conversation_id: str
    platform: str
    channel_type: str
    creator_id: str
    creator_aliases: list[str]
    media_id: str
    media_name: str
    role: str
    raw_text: str
    clean_text: str
    timestamp: int
    formatted_time: str
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    evidence_span: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    conversation_title: str = ""
    seq_num: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BriefCard:
    brief_card_id: str
    conversation_id: str
    creator_id: str
    knowledge_base: str
    source_message_id: str
    source_message_ids: list[str]
    platform: str
    brand: str | None
    product: str | None
    deliverable_type: str | None
    content_direction: str | None
    schedule_window: str | None
    rights_requirements: list[str] = field(default_factory=list)
    distribution_requirements: list[str] = field(default_factory=list)
    must_confirm_items: list[str] = field(default_factory=list)
    negotiable_items: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NegotiationEpisode:
    episode_id: str
    conversation_id: str
    creator_id: str
    knowledge_base: str
    workflow_stage: str
    episode_goal: str
    objection_type: str
    agency_strategy: list[str]
    creator_response_type: str
    outcome: str
    evidence_message_ids: list[str]
    message_ids: list[str]
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    creator_traits: list[CreatorTraitEvidence] = field(default_factory=list)
    listed_price: float | None = None
    target_price: float | None = None
    current_rebate_rate: float | None = None
    target_rebate_rate: float | None = None
    rebate_target_status: str = "unknown"
    agency_margin_pressure: str = "unknown"
    rights_gap_status: str = "unknown"
    payment_blocker_type: str = "unknown"
    summary: str = ""
    confidence: float = 0.5
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["creator_traits"] = [trait.to_dict() for trait in self.creator_traits]
        return data


@dataclass
class TalkTemplate:
    template_id: str
    knowledge_base: str
    scenario_key: str
    workflow_stage: str
    template_text: str
    slots: list[str] = field(default_factory=list)
    applicable_conditions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    source_message_ids: list[str] = field(default_factory=list)
    origin: str = "conversation_mined"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowPlaybookStep:
    step_id: str
    knowledge_base: str
    workflow_stage: str
    trigger_condition: str
    required_inputs: list[str]
    recommended_action: str
    fallback_action: str
    exit_condition: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalChunk:
    chunk_id: str
    chunk_type: str
    workflow_stage: str
    scenario_key: str
    knowledge_base: str
    embedding_text: str
    filter_tags: list[str] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
