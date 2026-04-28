from __future__ import annotations

from dataclasses import dataclass

from app import models


@dataclass(frozen=True)
class AssetConfig:
    asset_type: str
    file_name: str
    label: str
    id_field: str
    usage_group: str
    model: type
    searchable_fields: tuple[str, ...]


DATA_ASSETS: dict[str, AssetConfig] = {
    "conversation_messages": AssetConfig(
        asset_type="conversation_messages",
        file_name="conversation_messages.jsonl",
        label="标准化消息",
        id_field="message_id",
        usage_group="database",
        model=models.ConversationMessageRaw,
        searchable_fields=("message_id", "conversation_id", "creator_id", "role", "clean_text", "raw_text"),
    ),
    "brief_cards": AssetConfig(
        asset_type="brief_cards",
        file_name="brief_cards.jsonl",
        label="Brief 知识卡",
        id_field="brief_card_id",
        usage_group="brief_library",
        model=models.BriefCardRaw,
        searchable_fields=("brief_card_id", "conversation_id", "creator_id", "brand", "product", "knowledge_base"),
    ),
    "negotiation_episodes": AssetConfig(
        asset_type="negotiation_episodes",
        file_name="negotiation_episodes.jsonl",
        label="谈判片段",
        id_field="episode_id",
        usage_group="negotiation_library",
        model=models.NegotiationEpisodeRaw,
        searchable_fields=("episode_id", "conversation_id", "creator_id", "workflow_stage", "episode_goal", "summary"),
    ),
    "talk_templates": AssetConfig(
        asset_type="talk_templates",
        file_name="talk_templates.jsonl",
        label="话术模板",
        id_field="template_id",
        usage_group="talk_library",
        model=models.TalkTemplateRaw,
        searchable_fields=("template_id", "workflow_stage", "scenario_key", "template_text", "knowledge_base"),
    ),
    "workflow_playbook": AssetConfig(
        asset_type="workflow_playbook",
        file_name="workflow_playbook.jsonl",
        label="履约 SOP",
        id_field="step_id",
        usage_group="fulfillment_sop",
        model=models.WorkflowPlaybookRaw,
        searchable_fields=("step_id", "workflow_stage", "recommended_action", "knowledge_base"),
    ),
    "retrieval_chunks": AssetConfig(
        asset_type="retrieval_chunks",
        file_name="retrieval_chunks.jsonl",
        label="检索切片",
        id_field="chunk_id",
        usage_group="retrieval_library",
        model=models.RetrievalChunkRaw,
        searchable_fields=("chunk_id", "workflow_stage", "scenario_key", "embedding_text", "knowledge_base"),
    ),
    "gold_episode_review_queue": AssetConfig(
        asset_type="gold_episode_review_queue",
        file_name="gold_episode_review_queue.jsonl",
        label="人工审核队列",
        id_field="review_id",
        usage_group="review_queue",
        model=models.GoldReviewTaskRaw,
        searchable_fields=("review_id", "episode_id", "creator_id", "workflow_stage", "review_status"),
    ),
}

DOC_ASSETS: dict[str, str] = {
    "tag_dictionary": "tag_dictionary.yaml",
    "annotation_guideline": "annotation_guideline.md",
    "asset_field_guide": "asset_field_guide.md",
}

ASSET_ORDER = [
    "conversation_messages",
    "brief_cards",
    "negotiation_episodes",
    "talk_templates",
    "workflow_playbook",
    "retrieval_chunks",
    "gold_episode_review_queue",
]

USAGE_GROUPS: dict[str, list[str]] = {
    "brief_knowledge": ["brief_cards"],
    "negotiation_knowledge": ["negotiation_episodes"],
    "talk_library": ["talk_templates"],
    "fulfillment_sop": ["workflow_playbook"],
    "retrieval_library": ["retrieval_chunks"],
    "review_queue": ["gold_episode_review_queue"],
    "database": ["conversation_messages"],
    "docs": ["tag_dictionary", "annotation_guideline", "asset_field_guide"],
}
