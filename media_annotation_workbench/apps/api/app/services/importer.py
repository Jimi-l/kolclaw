from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.services.asset_registry import ASSET_ORDER, DATA_ASSETS, DOC_ASSETS


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _build_raw_model(asset_type: str, snapshot_id: str, payload: dict[str, Any]):
    if asset_type == "conversation_messages":
        return models.ConversationMessageRaw(
            snapshot_id=snapshot_id,
            message_id=payload["message_id"],
            conversation_id=payload.get("conversation_id"),
            creator_id=payload.get("creator_id"),
            role=payload.get("role"),
            seq_num=payload.get("seq_num"),
            raw_payload=payload,
        )
    if asset_type == "brief_cards":
        return models.BriefCardRaw(
            snapshot_id=snapshot_id,
            brief_card_id=payload["brief_card_id"],
            conversation_id=payload.get("conversation_id"),
            creator_id=payload.get("creator_id"),
            knowledge_base=payload.get("knowledge_base"),
            raw_payload=payload,
        )
    if asset_type == "negotiation_episodes":
        return models.NegotiationEpisodeRaw(
            snapshot_id=snapshot_id,
            episode_id=payload["episode_id"],
            conversation_id=payload.get("conversation_id"),
            creator_id=payload.get("creator_id"),
            knowledge_base=payload.get("knowledge_base"),
            workflow_stage=payload.get("workflow_stage"),
            episode_goal=payload.get("episode_goal"),
            objection_type=payload.get("objection_type"),
            raw_payload=payload,
        )
    if asset_type == "talk_templates":
        return models.TalkTemplateRaw(
            snapshot_id=snapshot_id,
            template_id=payload["template_id"],
            knowledge_base=payload.get("knowledge_base"),
            workflow_stage=payload.get("workflow_stage"),
            scenario_key=payload.get("scenario_key"),
            raw_payload=payload,
        )
    if asset_type == "workflow_playbook":
        return models.WorkflowPlaybookRaw(
            snapshot_id=snapshot_id,
            step_id=payload["step_id"],
            knowledge_base=payload.get("knowledge_base"),
            workflow_stage=payload.get("workflow_stage"),
            raw_payload=payload,
        )
    if asset_type == "retrieval_chunks":
        metadata = payload.get("metadata") or {}
        return models.RetrievalChunkRaw(
            snapshot_id=snapshot_id,
            chunk_id=payload["chunk_id"],
            creator_id=metadata.get("creator_id"),
            episode_id=metadata.get("episode_id"),
            knowledge_base=payload.get("knowledge_base"),
            workflow_stage=payload.get("workflow_stage"),
            scenario_key=payload.get("scenario_key"),
            raw_payload=payload,
        )
    if asset_type == "gold_episode_review_queue":
        return models.GoldReviewTaskRaw(
            snapshot_id=snapshot_id,
            review_id=payload["review_id"],
            episode_id=payload.get("episode_id"),
            conversation_id=payload.get("conversation_id"),
            creator_id=payload.get("creator_id"),
            workflow_stage=payload.get("workflow_stage"),
            episode_goal=payload.get("episode_goal"),
            objection_type=payload.get("objection_type"),
            priority=payload.get("priority"),
            review_status=payload.get("review_status"),
            raw_payload=payload,
        )
    raise KeyError(f"Unsupported asset_type={asset_type}")


def _create_review_task(snapshot_id: str, payload: dict[str, Any]) -> models.ReviewTask:
    return models.ReviewTask(
        snapshot_id=snapshot_id,
        raw_review_id=payload["review_id"],
        episode_id=payload["episode_id"],
        conversation_id=payload.get("conversation_id"),
        creator_id=payload.get("creator_id"),
        priority=payload.get("priority") or "medium",
        status=payload.get("review_status") or "pending",
    )


def _create_import_event(snapshot_id: str, review_task_id: str) -> models.ReviewEvent:
    return models.ReviewEvent(
        review_task_id=review_task_id,
        snapshot_id=snapshot_id,
        actor_user_id=None,
        event_type="imported",
        note="任务由快照导入生成。",
        payload={},
    )


def import_snapshot(session: Session, source_dir: str | Path, *, activate: bool = True) -> models.Snapshot:
    source_path = Path(source_dir).expanduser().resolve()
    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError(f"Snapshot source directory does not exist: {source_path}")

    required_doc_types = ("tag_dictionary", "annotation_guideline")
    required_paths = [source_path / DATA_ASSETS[asset_type].file_name for asset_type in ASSET_ORDER]
    required_paths.extend(source_path / DOC_ASSETS[doc_type] for doc_type in required_doc_types)

    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Snapshot directory is missing required files: {missing}")

    snapshot = models.Snapshot(source_dir=str(source_path))
    session.add(snapshot)
    session.flush()

    asset_counts: dict[str, int] = {}
    file_hashes: dict[str, str] = {}

    if activate:
        session.execute(update(models.Snapshot).values(is_active=False))
        snapshot.is_active = True
    else:
        active_snapshot = session.scalar(select(models.Snapshot).where(models.Snapshot.is_active.is_(True)))
        snapshot.is_active = active_snapshot is None

    for asset_type in ASSET_ORDER:
        config = DATA_ASSETS[asset_type]
        path = source_path / config.file_name
        file_hashes[config.file_name] = _sha256(path)
        rows = _load_jsonl(path)
        asset_counts[asset_type] = len(rows)
        for payload in rows:
            session.add(_build_raw_model(asset_type, snapshot.snapshot_id, payload))
            if asset_type == "gold_episode_review_queue":
                review_task = _create_review_task(snapshot.snapshot_id, payload)
                session.add(review_task)
                session.flush()
                session.add(_create_import_event(snapshot.snapshot_id, review_task.review_task_id))

    for doc_type, file_name in DOC_ASSETS.items():
        path = source_path / file_name
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        file_hashes[file_name] = _sha256(path)
        asset_counts[doc_type] = 1
        session.add(
            models.DocumentVersion(
                snapshot_id=snapshot.snapshot_id,
                doc_type=doc_type,
                content=content,
                content_hash=file_hashes[file_name],
            )
        )

    snapshot.asset_counts = asset_counts
    snapshot.file_hashes = file_hashes

    session.commit()
    session.refresh(snapshot)
    return snapshot
