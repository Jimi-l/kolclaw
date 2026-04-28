from __future__ import annotations

import json
from collections import Counter
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.schemas import ReviewEventResponse, ReviewTaskListItem, SnapshotResponse, UserInfo
from app.services.asset_registry import ASSET_ORDER, DATA_ASSETS, DOC_ASSETS, USAGE_GROUPS
from app.services.display_labels import (
    ASSET_TYPE_LABELS,
    EPISODE_GOAL_LABELS,
    KNOWLEDGE_BASE_LABELS,
    OBJECTION_TYPE_LABELS,
    OUTCOME_LABELS,
    PRIORITY_LABELS,
    REVIEW_EVENT_LABELS,
    REVIEW_STATUS_LABELS,
    ROLE_LABELS,
    USER_ROLE_LABELS,
    WORKFLOW_STAGE_DESCRIPTIONS,
    WORKFLOW_STAGE_SHORT_LABELS,
    label_for,
    make_option_items,
)


FILTERABLE_FIELDS = (
    "workflow_stage",
    "episode_goal",
    "objection_type",
    "creator_id",
    "knowledge_base",
    "review_status",
    "conversation_id",
    "priority",
    "status",
)


def serialize_snapshot(snapshot: models.Snapshot) -> SnapshotResponse:
    return SnapshotResponse(
        snapshot_id=snapshot.snapshot_id,
        source_dir=snapshot.source_dir,
        imported_at=snapshot.imported_at,
        is_active=snapshot.is_active,
        asset_counts=snapshot.asset_counts or {},
        file_hashes=snapshot.file_hashes or {},
    )


def serialize_user(user: models.User | None) -> UserInfo | None:
    if not user:
        return None
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        role_label=label_for(USER_ROLE_LABELS, user.role, user.role) or user.role,
    )


def _build_asset_display(asset_type: str, item: dict[str, Any]) -> dict[str, Any] | None:
    if asset_type == "brief_cards":
        return {
            "标题": item.get("brand") or item.get("product") or item.get("brief_card_id") or "未命名需求卡",
            "知识库": label_for(KNOWLEDGE_BASE_LABELS, item.get("knowledge_base"), item.get("knowledge_base")),
            "平台": item.get("platform") or "—",
            "品牌": item.get("brand") or "—",
            "产品": item.get("product") or "—",
            "档期": item.get("schedule_window") or "—",
        }
    if asset_type == "negotiation_episodes":
        return {
            "标题": item.get("summary") or item.get("episode_id") or "未命名片段",
            "阶段": label_for(WORKFLOW_STAGE_SHORT_LABELS, item.get("workflow_stage"), item.get("workflow_stage")),
            "目标": label_for(EPISODE_GOAL_LABELS, item.get("episode_goal"), item.get("episode_goal")),
            "阻力": label_for(OBJECTION_TYPE_LABELS, item.get("objection_type"), item.get("objection_type")),
            "审核状态": label_for(REVIEW_STATUS_LABELS, item.get("review_status"), item.get("review_status") or "未进入审核"),
            "知识库": label_for(KNOWLEDGE_BASE_LABELS, item.get("knowledge_base"), item.get("knowledge_base")),
        }
    if asset_type == "gold_episode_review_queue":
        return {
            "审核任务": item.get("review_id") or item.get("review_task_id") or "—",
            "阶段": label_for(WORKFLOW_STAGE_SHORT_LABELS, item.get("workflow_stage"), item.get("workflow_stage")),
            "目标": label_for(EPISODE_GOAL_LABELS, item.get("episode_goal"), item.get("episode_goal")),
            "阻力": label_for(OBJECTION_TYPE_LABELS, item.get("objection_type"), item.get("objection_type")),
            "审核状态": label_for(REVIEW_STATUS_LABELS, item.get("review_status"), item.get("review_status")),
            "优先级": label_for(PRIORITY_LABELS, item.get("priority"), item.get("priority")),
        }
    return None


def _decorate_asset_item(asset_type: str, item: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(item)
    display = _build_asset_display(asset_type, decorated)
    if display:
        decorated["display"] = display
    return decorated


def _build_evidence_chat_messages(episode_payload: dict[str, Any], evidence_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    direct_message_ids = set(episode_payload.get("evidence_message_ids") or [])
    chat_messages: list[dict[str, Any]] = []

    for message in evidence_messages:
        role = message.get("role")
        role_label = label_for(ROLE_LABELS, role, role or "消息")
        creator_aliases = message.get("creator_aliases") or []
        media_name = message.get("media_name")
        if role == "agency":
            speaker_name = media_name or message.get("media_id") or role_label or "媒介"
        else:
            speaker_name = creator_aliases[0] if creator_aliases else message.get("creator_id") or role_label or "达人"

        chat_messages.append(
            {
                "message_id": message.get("message_id"),
                "seq_num": message.get("seq_num"),
                "role": role,
                "role_label": role_label,
                "speaker_name": speaker_name,
                "speaker_badge": role_label or "消息",
                "formatted_time": message.get("formatted_time"),
                "clean_text": message.get("clean_text") or "（空消息）",
                "raw_text": message.get("raw_text") or message.get("clean_text") or "（空消息）",
                "is_direct_evidence": message.get("message_id") in direct_message_ids,
                "creator_aliases": creator_aliases,
                "media_name": media_name,
            }
        )
    return chat_messages


def _build_display_labels(episode_payload: dict[str, Any], task: models.ReviewTask | None) -> dict[str, str | None]:
    return {
        "workflow_stage": label_for(WORKFLOW_STAGE_SHORT_LABELS, episode_payload.get("workflow_stage"), episode_payload.get("workflow_stage")),
        "episode_goal": label_for(EPISODE_GOAL_LABELS, episode_payload.get("episode_goal"), episode_payload.get("episode_goal")),
        "objection_type": label_for(OBJECTION_TYPE_LABELS, episode_payload.get("objection_type"), episode_payload.get("objection_type")),
        "outcome": label_for(OUTCOME_LABELS, episode_payload.get("outcome"), episode_payload.get("outcome")),
        "status": label_for(REVIEW_STATUS_LABELS, task.status if task else None, task.status if task else None),
    }


def _build_field_options() -> dict[str, list[dict[str, Any]]]:
    return {
        "workflow_stage": make_option_items(WORKFLOW_STAGE_SHORT_LABELS, WORKFLOW_STAGE_DESCRIPTIONS),
        "episode_goal": make_option_items(EPISODE_GOAL_LABELS),
        "objection_type": make_option_items(OBJECTION_TYPE_LABELS),
        "outcome": make_option_items(OUTCOME_LABELS),
    }


def get_snapshot(session: Session, snapshot_id: str | None) -> models.Snapshot | None:
    if snapshot_id:
        return session.scalar(select(models.Snapshot).where(models.Snapshot.snapshot_id == snapshot_id))
    return session.scalar(
        select(models.Snapshot)
        .where(models.Snapshot.is_active.is_(True))
        .order_by(models.Snapshot.imported_at.desc())
    )


def list_snapshots(session: Session) -> list[models.Snapshot]:
    return session.scalars(select(models.Snapshot).order_by(models.Snapshot.imported_at.desc())).all()


def get_review_tasks_by_snapshot(session: Session, snapshot_id: str) -> list[models.ReviewTask]:
    return session.scalars(
        select(models.ReviewTask)
        .where(models.ReviewTask.snapshot_id == snapshot_id)
        .order_by(models.ReviewTask.updated_at.desc())
    ).all()


def get_latest_edit_map(session: Session, snapshot_id: str) -> dict[str, models.EpisodeReviewEdit]:
    edits = session.scalars(
        select(models.EpisodeReviewEdit)
        .where(models.EpisodeReviewEdit.snapshot_id == snapshot_id)
        .order_by(models.EpisodeReviewEdit.created_at.desc())
    ).all()
    latest: dict[str, models.EpisodeReviewEdit] = {}
    for edit in edits:
        latest.setdefault(edit.review_task_id, edit)
    return latest


def _find_raw_review_task(session: Session, snapshot_id: str, raw_review_id: str) -> models.GoldReviewTaskRaw | None:
    return session.scalar(
        select(models.GoldReviewTaskRaw).where(
            models.GoldReviewTaskRaw.snapshot_id == snapshot_id,
            models.GoldReviewTaskRaw.review_id == raw_review_id,
        )
    )


def _overlay_episode(raw_payload: dict[str, Any], edit: models.EpisodeReviewEdit | None, task: models.ReviewTask | None) -> dict[str, Any]:
    item = dict(raw_payload)
    if edit:
        for field in ("workflow_stage", "episode_goal", "objection_type", "creator_traits", "outcome", "confidence"):
            value = getattr(edit, field)
            if value is not None:
                item[field] = value
        if edit.review_notes is not None:
            item["review_notes"] = edit.review_notes
    if task:
        item["review_status"] = task.status
        item["review_task_id"] = task.review_task_id
    return item


def _merge_review_item(raw_payload: dict[str, Any], task: models.ReviewTask | None, edit: models.EpisodeReviewEdit | None) -> dict[str, Any]:
    item = dict(raw_payload)
    if task:
        item["review_status"] = task.status
        item["review_task_id"] = task.review_task_id
        item["assigned_user_id"] = task.assigned_user_id
    if edit and edit.review_notes is not None:
        item["review_notes"] = edit.review_notes
    return item


def _searchable_blob(item: dict[str, Any], fields: Iterable[str]) -> str:
    values: list[str] = []
    for field in fields:
        value = item.get(field)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            values.append(json.dumps(value, ensure_ascii=False))
        else:
            values.append(str(value))
    values.append(json.dumps(item, ensure_ascii=False))
    return " ".join(values).lower()


def _passes_filters(item: dict[str, Any], filters: dict[str, str]) -> bool:
    for key, value in filters.items():
        if not value:
            continue
        item_value = item.get(key)
        if item_value is None:
            return False
        if str(item_value) != value:
            return False
    return True


def _sort_value(item: dict[str, Any], sort_by: str | None):
    if not sort_by:
        return ""
    value = item.get(sort_by)
    if value is None:
        return ""
    return value


def list_asset_items(
    session: Session,
    asset_type: str,
    *,
    snapshot_id: str | None,
    view: str,
    search: str | None,
    filters: dict[str, str],
    sort_by: str | None,
    sort_dir: str,
    offset: int,
    limit: int,
) -> tuple[str, list[dict[str, Any]], int]:
    snapshot = get_snapshot(session, snapshot_id)
    if not snapshot:
        raise LookupError("No snapshot found.")

    if asset_type not in DATA_ASSETS:
        raise KeyError(asset_type)

    config = DATA_ASSETS[asset_type]
    rows = session.scalars(
        select(config.model).where(config.model.snapshot_id == snapshot.snapshot_id)
    ).all()

    tasks = {task.raw_review_id: task for task in get_review_tasks_by_snapshot(session, snapshot.snapshot_id)}
    latest_edits = get_latest_edit_map(session, snapshot.snapshot_id)

    items: list[dict[str, Any]] = []
    for row in rows:
        raw_payload = dict(row.raw_payload)
        if asset_type == "negotiation_episodes":
            task = next((task for task in tasks.values() if task.episode_id == row.episode_id), None)
            edit = latest_edits.get(task.review_task_id) if task else None
            item = _overlay_episode(raw_payload, edit if view == "reviewed" else None, task if view == "reviewed" else None)
        elif asset_type == "gold_episode_review_queue":
            task = tasks.get(row.review_id)
            edit = latest_edits.get(task.review_task_id) if task else None
            item = _merge_review_item(raw_payload, task, edit)
        else:
            item = raw_payload
        items.append(_decorate_asset_item(asset_type, item))

    if search:
        search_lower = search.lower()
        items = [item for item in items if search_lower in _searchable_blob(item, config.searchable_fields)]

    items = [item for item in items if _passes_filters(item, filters)]
    reverse = sort_dir.lower() == "desc"
    if sort_by:
        items.sort(key=lambda item: _sort_value(item, sort_by), reverse=reverse)
    elif asset_type == "conversation_messages":
        items.sort(key=lambda item: item.get("seq_num") or 0)

    total = len(items)
    paged = items[offset : offset + limit]
    return snapshot.snapshot_id, paged, total


def _find_episode_by_id(session: Session, snapshot_id: str, episode_id: str) -> models.NegotiationEpisodeRaw | None:
    return session.scalar(
        select(models.NegotiationEpisodeRaw).where(
            models.NegotiationEpisodeRaw.snapshot_id == snapshot_id,
            models.NegotiationEpisodeRaw.episode_id == episode_id,
        )
    )


def _find_review_task_by_episode(session: Session, snapshot_id: str, episode_id: str) -> models.ReviewTask | None:
    return session.scalar(
        select(models.ReviewTask).where(
            models.ReviewTask.snapshot_id == snapshot_id,
            models.ReviewTask.episode_id == episode_id,
        )
    )


def _find_latest_edit_for_task(session: Session, review_task_id: str | None) -> models.EpisodeReviewEdit | None:
    if not review_task_id:
        return None
    return session.scalar(
        select(models.EpisodeReviewEdit)
        .where(models.EpisodeReviewEdit.review_task_id == review_task_id)
        .order_by(models.EpisodeReviewEdit.created_at.desc())
    )


def _find_related_for_episode(
    session: Session,
    snapshot_id: str,
    episode_payload: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    episode_id = episode_payload.get("episode_id")
    conversation_id = episode_payload.get("conversation_id")
    creator_id = episode_payload.get("creator_id")
    message_ids = set((episode_payload.get("message_ids") or []) + (episode_payload.get("evidence_message_ids") or []))

    evidence_messages = [
        row.raw_payload
        for row in session.scalars(
            select(models.ConversationMessageRaw).where(
                models.ConversationMessageRaw.snapshot_id == snapshot_id,
                models.ConversationMessageRaw.message_id.in_(message_ids),
            )
        ).all()
    ] if message_ids else []
    evidence_messages.sort(key=lambda item: item.get("seq_num") or 0)

    briefs = [
        row.raw_payload
        for row in session.scalars(
            select(models.BriefCardRaw).where(
                models.BriefCardRaw.snapshot_id == snapshot_id,
                models.BriefCardRaw.creator_id == creator_id,
            )
        ).all()
        if not conversation_id or row.conversation_id == conversation_id
    ]

    templates = [
        row.raw_payload
        for row in session.scalars(
            select(models.TalkTemplateRaw).where(
                models.TalkTemplateRaw.snapshot_id == snapshot_id,
            )
        ).all()
        if episode_id in (row.raw_payload.get("source_episode_ids") or [])
    ]

    chunks = [
        row.raw_payload
        for row in session.scalars(
            select(models.RetrievalChunkRaw).where(
                models.RetrievalChunkRaw.snapshot_id == snapshot_id,
            )
        ).all()
        if row.episode_id == episode_id or (set(ref.get("message_id", "") for ref in row.raw_payload.get("source_refs") or []) & message_ids)
    ]

    review_items = [
        row.raw_payload
        for row in session.scalars(
            select(models.GoldReviewTaskRaw).where(
                models.GoldReviewTaskRaw.snapshot_id == snapshot_id,
                models.GoldReviewTaskRaw.episode_id == episode_id,
            )
        ).all()
    ]

    return {
        "conversation_messages": evidence_messages,
        "brief_cards": briefs,
        "talk_templates": templates,
        "retrieval_chunks": chunks,
        "gold_episode_review_queue": review_items,
    }


def get_asset_detail(
    session: Session,
    asset_type: str,
    item_id: str,
    *,
    snapshot_id: str | None,
    view: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None, str | None, dict[str, list[dict[str, Any]]], str | None, str | None]:
    snapshot = get_snapshot(session, snapshot_id)
    if not snapshot:
        raise LookupError("No snapshot found.")

    if asset_type in DOC_ASSETS:
        document = session.scalar(
            select(models.DocumentVersion).where(
                models.DocumentVersion.snapshot_id == snapshot.snapshot_id,
                models.DocumentVersion.doc_type == asset_type,
            )
        )
        if not document:
            raise LookupError(f"Document not found: {asset_type}")
        document_format = "markdown" if asset_type.endswith("guide") or asset_type.endswith("guideline") else "yaml"
        return snapshot.snapshot_id, None, None, None, {}, document.content, document_format

    if asset_type not in DATA_ASSETS:
        raise KeyError(asset_type)

    config = DATA_ASSETS[asset_type]
    row = session.scalar(
        select(config.model).where(
            config.model.snapshot_id == snapshot.snapshot_id,
            getattr(config.model, config.id_field) == item_id,
        )
    )
    if not row:
        raise LookupError(f"Asset not found: {asset_type}/{item_id}")

    raw_item = dict(row.raw_payload)
    related: dict[str, list[dict[str, Any]]] = {}
    reviewed_item: dict[str, Any] | None = None
    review_status: str | None = None

    if asset_type == "negotiation_episodes":
        task = _find_review_task_by_episode(session, snapshot.snapshot_id, row.episode_id)
        edit = _find_latest_edit_for_task(session, task.review_task_id if task else None)
        reviewed_item = _overlay_episode(raw_item, edit if view == "reviewed" else None, task if view == "reviewed" else None)
        review_status = task.status if task else None
        related = _find_related_for_episode(session, snapshot.snapshot_id, raw_item)
    elif asset_type == "gold_episode_review_queue":
        task = session.scalar(
            select(models.ReviewTask).where(
                models.ReviewTask.snapshot_id == snapshot.snapshot_id,
                models.ReviewTask.raw_review_id == row.review_id,
            )
        )
        edit = _find_latest_edit_for_task(session, task.review_task_id if task else None)
        reviewed_item = _merge_review_item(raw_item, task, edit)
        review_status = task.status if task else None
        if row.episode_id:
            episode = _find_episode_by_id(session, snapshot.snapshot_id, row.episode_id)
            if episode:
                related = _find_related_for_episode(session, snapshot.snapshot_id, episode.raw_payload)
    else:
        reviewed_item = raw_item
        if asset_type == "brief_cards":
            related = {
                "negotiation_episodes": [
                    episode.raw_payload
                    for episode in session.scalars(
                        select(models.NegotiationEpisodeRaw).where(
                            models.NegotiationEpisodeRaw.snapshot_id == snapshot.snapshot_id,
                            models.NegotiationEpisodeRaw.creator_id == row.creator_id,
                        )
                    ).all()
                    if not row.conversation_id or episode.conversation_id == row.conversation_id
                ]
            }
        elif asset_type == "talk_templates":
            episode_ids = set(raw_item.get("source_episode_ids") or [])
            related = {
                "negotiation_episodes": [
                    episode.raw_payload
                    for episode in session.scalars(
                        select(models.NegotiationEpisodeRaw).where(
                            models.NegotiationEpisodeRaw.snapshot_id == snapshot.snapshot_id,
                        )
                    ).all()
                    if episode.episode_id in episode_ids
                ]
            }
        elif asset_type == "retrieval_chunks":
            episode_id = raw_item.get("metadata", {}).get("episode_id")
            if episode_id:
                episode = _find_episode_by_id(session, snapshot.snapshot_id, episode_id)
                related = {"negotiation_episodes": [episode.raw_payload] if episode else []}

    return snapshot.snapshot_id, raw_item, reviewed_item, review_status, related, None, None


def build_dashboard_summary(session: Session, default_snapshot_dir: str) -> dict[str, Any]:
    snapshots = list_snapshots(session)
    active_snapshot = next((snapshot for snapshot in snapshots if snapshot.is_active), None)
    active_snapshot_id = active_snapshot.snapshot_id if active_snapshot else None
    review_counts = Counter()
    stage_distribution = Counter()

    if active_snapshot_id:
        tasks = get_review_tasks_by_snapshot(session, active_snapshot_id)
        review_counts.update(task.status for task in tasks)
        latest_edits = get_latest_edit_map(session, active_snapshot_id)
        for episode in session.scalars(
            select(models.NegotiationEpisodeRaw).where(models.NegotiationEpisodeRaw.snapshot_id == active_snapshot_id)
        ).all():
            task = _find_review_task_by_episode(session, active_snapshot_id, episode.episode_id)
            edit = latest_edits.get(task.review_task_id) if task else None
            payload = _overlay_episode(episode.raw_payload, edit, task)
            if payload.get("workflow_stage"):
                stage_distribution[payload["workflow_stage"]] += 1

    asset_counts = active_snapshot.asset_counts if active_snapshot else {}
    asset_count_cards = [
        {
            "key": asset_type,
            "label": label_for(ASSET_TYPE_LABELS, asset_type, asset_type),
            "count": asset_counts.get(asset_type, 0),
        }
        for asset_type in [*ASSET_ORDER, "tag_dictionary", "annotation_guideline", "asset_field_guide"]
        if asset_type in asset_counts
    ]
    review_status_cards = [
        {
            "key": status,
            "label": label_for(REVIEW_STATUS_LABELS, status, status),
            "count": count,
        }
        for status, count in sorted(review_counts.items(), key=lambda item: item[0])
    ]
    stage_distribution_cards = [
        {
            "key": stage,
            "label": label_for(WORKFLOW_STAGE_SHORT_LABELS, stage, stage),
            "description": label_for(WORKFLOW_STAGE_DESCRIPTIONS, stage, None),
            "count": count,
        }
        for stage, count in sorted(stage_distribution.items(), key=lambda item: item[0])
    ]

    return {
        "active_snapshot": serialize_snapshot(active_snapshot) if active_snapshot else None,
        "asset_counts": asset_counts,
        "review_counts": dict(review_counts),
        "stage_distribution": dict(stage_distribution),
        "asset_count_cards": asset_count_cards,
        "review_status_cards": review_status_cards,
        "stage_distribution_cards": stage_distribution_cards,
        "recent_imports": [serialize_snapshot(snapshot) for snapshot in snapshots[:5]],
        "usage_groups": USAGE_GROUPS,
        "default_snapshot_dir": default_snapshot_dir,
    }


def serialize_review_task(session: Session, task: models.ReviewTask) -> ReviewTaskListItem:
    raw_row = _find_raw_review_task(session, task.snapshot_id, task.raw_review_id)
    assigned_user = session.scalar(select(models.User).where(models.User.user_id == task.assigned_user_id)) if task.assigned_user_id else None
    raw_payload = raw_row.raw_payload if raw_row else {}
    workflow_stage = raw_payload.get("workflow_stage")
    episode_goal = raw_payload.get("episode_goal")
    objection_type = raw_payload.get("objection_type")
    return ReviewTaskListItem(
        review_task_id=task.review_task_id,
        raw_review_id=task.raw_review_id,
        snapshot_id=task.snapshot_id,
        episode_id=task.episode_id,
        conversation_id=task.conversation_id,
        creator_id=task.creator_id,
        priority=task.priority,
        priority_label=label_for(PRIORITY_LABELS, task.priority, task.priority) or task.priority,
        status=task.status,
        status_label=label_for(REVIEW_STATUS_LABELS, task.status, task.status) or task.status,
        workflow_stage=workflow_stage,
        workflow_stage_label=label_for(WORKFLOW_STAGE_SHORT_LABELS, workflow_stage, workflow_stage),
        episode_goal=episode_goal,
        episode_goal_label=label_for(EPISODE_GOAL_LABELS, episode_goal, episode_goal),
        objection_type=objection_type,
        objection_type_label=label_for(OBJECTION_TYPE_LABELS, objection_type, objection_type),
        assigned_user=serialize_user(assigned_user),
        updated_at=task.updated_at,
    )


def serialize_review_event(session: Session, event: models.ReviewEvent) -> ReviewEventResponse:
    actor = session.scalar(select(models.User).where(models.User.user_id == event.actor_user_id)) if event.actor_user_id else None
    return ReviewEventResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        event_type_label=label_for(REVIEW_EVENT_LABELS, event.event_type, event.event_type) or event.event_type,
        note=event.note,
        payload=event.payload,
        created_at=event.created_at,
        actor=serialize_user(actor),
    )


def get_document(session: Session, doc_type: str, snapshot_id: str | None) -> tuple[str, str, str]:
    snapshot = get_snapshot(session, snapshot_id)
    if not snapshot:
        raise LookupError("No snapshot found.")
    document = session.scalar(
        select(models.DocumentVersion).where(
            models.DocumentVersion.snapshot_id == snapshot.snapshot_id,
            models.DocumentVersion.doc_type == doc_type,
        )
    )
    if not document:
        raise LookupError(f"Document not found: {doc_type}")
    file_name = DOC_ASSETS[doc_type]
    if file_name.endswith(".yaml"):
        format_name = "yaml"
    else:
        format_name = "markdown"
    return snapshot.snapshot_id, document.content, format_name


def list_review_tasks(
    session: Session,
    *,
    snapshot_id: str | None,
    search: str | None,
    filters: dict[str, str],
) -> tuple[str, list[models.ReviewTask]]:
    snapshot = get_snapshot(session, snapshot_id)
    if not snapshot:
        raise LookupError("No snapshot found.")
    items = get_review_tasks_by_snapshot(session, snapshot.snapshot_id)
    if filters.get("review_status"):
        items = [task for task in items if task.status == filters["review_status"]]
    if filters.get("creator_id"):
        items = [task for task in items if task.creator_id == filters["creator_id"]]
    if search:
        search_lower = search.lower()
        filtered: list[models.ReviewTask] = []
        for task in items:
            raw_row = _find_raw_review_task(session, task.snapshot_id, task.raw_review_id)
            blob = json.dumps(raw_row.raw_payload if raw_row else {}, ensure_ascii=False).lower()
            if search_lower in blob or search_lower in task.episode_id.lower():
                filtered.append(task)
        items = filtered
    return snapshot.snapshot_id, items


def get_review_task_detail(session: Session, review_task_id: str) -> dict[str, Any]:
    task = session.scalar(select(models.ReviewTask).where(models.ReviewTask.review_task_id == review_task_id))
    if not task:
        raise LookupError(f"Review task not found: {review_task_id}")

    raw_row = _find_raw_review_task(session, task.snapshot_id, task.raw_review_id)
    raw_episode_row = _find_episode_by_id(session, task.snapshot_id, task.episode_id)
    latest_edit = _find_latest_edit_for_task(session, task.review_task_id)
    raw_episode = raw_episode_row.raw_payload if raw_episode_row else None
    reviewed_episode = _overlay_episode(raw_episode, latest_edit, task) if raw_episode else None
    related_assets = _find_related_for_episode(session, task.snapshot_id, raw_episode or {}) if raw_episode else {}
    events = session.scalars(
        select(models.ReviewEvent)
        .where(models.ReviewEvent.review_task_id == task.review_task_id)
        .order_by(models.ReviewEvent.created_at.asc())
    ).all()

    return {
        "task": serialize_review_task(session, task),
        "raw_review_item": raw_row.raw_payload if raw_row else {},
        "raw_episode": raw_episode,
        "reviewed_episode": reviewed_episode,
        "latest_edit": {
            "edit_id": latest_edit.edit_id,
            "workflow_stage": latest_edit.workflow_stage,
            "episode_goal": latest_edit.episode_goal,
            "objection_type": latest_edit.objection_type,
            "creator_traits": latest_edit.creator_traits,
            "outcome": latest_edit.outcome,
            "confidence": latest_edit.confidence,
            "review_notes": latest_edit.review_notes,
            "status_at_save": latest_edit.status_at_save,
            "created_at": latest_edit.created_at,
        } if latest_edit else None,
        "evidence_messages": related_assets.get("conversation_messages", []),
        "evidence_chat_messages": _build_evidence_chat_messages(reviewed_episode or raw_episode or {}, related_assets.get("conversation_messages", [])),
        "related_assets": related_assets,
        "display_labels": _build_display_labels(reviewed_episode or raw_episode or {}, task),
        "field_options": _build_field_options(),
        "events": [serialize_review_event(session, event) for event in events],
    }


def list_reviewed_episodes(session: Session, snapshot_id: str | None) -> tuple[str, list[dict[str, Any]]]:
    snapshot = get_snapshot(session, snapshot_id)
    if not snapshot:
        raise LookupError("No snapshot found.")
    tasks_by_episode = {
        task.episode_id: task
        for task in get_review_tasks_by_snapshot(session, snapshot.snapshot_id)
    }
    latest_edits = get_latest_edit_map(session, snapshot.snapshot_id)
    items: list[dict[str, Any]] = []
    for row in session.scalars(
        select(models.NegotiationEpisodeRaw).where(models.NegotiationEpisodeRaw.snapshot_id == snapshot.snapshot_id)
    ).all():
        task = tasks_by_episode.get(row.episode_id)
        edit = latest_edits.get(task.review_task_id) if task else None
        items.append(_overlay_episode(row.raw_payload, edit, task))
    return snapshot.snapshot_id, items
