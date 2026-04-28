from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Snapshot(Base):
    __tablename__ = "snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_dir: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    file_hashes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    asset_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ConversationMessageRaw(Base):
    __tablename__ = "conversation_messages_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "message_id", name="uq_conv_message_snapshot_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    message_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str] = mapped_column(String(128), index=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    seq_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class BriefCardRaw(Base):
    __tablename__ = "brief_cards_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "brief_card_id", name="uq_brief_snapshot_brief_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    brief_card_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    knowledge_base: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class NegotiationEpisodeRaw(Base):
    __tablename__ = "negotiation_episodes_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "episode_id", name="uq_episode_snapshot_episode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    episode_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    knowledge_base: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    episode_goal: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    objection_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class TalkTemplateRaw(Base):
    __tablename__ = "talk_templates_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "template_id", name="uq_template_snapshot_template"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    template_id: Mapped[str] = mapped_column(String(128), index=True)
    knowledge_base: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    scenario_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class WorkflowPlaybookRaw(Base):
    __tablename__ = "workflow_playbook_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "step_id", name="uq_playbook_snapshot_step"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    step_id: Mapped[str] = mapped_column(String(128), index=True)
    knowledge_base: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class RetrievalChunkRaw(Base):
    __tablename__ = "retrieval_chunks_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "chunk_id", name="uq_chunk_snapshot_chunk"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    chunk_id: Mapped[str] = mapped_column(String(128), index=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    episode_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    knowledge_base: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    scenario_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class GoldReviewTaskRaw(Base):
    __tablename__ = "gold_review_tasks_raw"
    __table_args__ = (UniqueConstraint("snapshot_id", "review_id", name="uq_review_snapshot_review"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    review_id: Mapped[str] = mapped_column(String(128), index=True)
    episode_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    episode_goal: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    objection_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("snapshot_id", "doc_type", name="uq_doc_snapshot_doc_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (UniqueConstraint("snapshot_id", "raw_review_id", name="uq_task_snapshot_raw_review"),)

    review_task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    raw_review_id: Mapped[str] = mapped_column(String(128), index=True)
    episode_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    creator_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    assigned_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    latest_edit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EpisodeReviewEdit(Base):
    __tablename__ = "episode_review_edits"

    edit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("review_tasks.review_task_id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    episode_id: Mapped[str] = mapped_column(String(128), index=True)
    edited_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.user_id"), index=True)
    workflow_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    episode_goal: Mapped[str | None] = mapped_column(String(64), nullable=True)
    objection_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creator_traits: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_at_save: Mapped[str] = mapped_column(String(32), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewEvent(Base):
    __tablename__ = "review_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    review_task_id: Mapped[str] = mapped_column(String(36), ForeignKey("review_tasks.review_task_id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("snapshots.snapshot_id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.user_id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
