from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.assets import get_review_task_detail


def _get_task(session: Session, review_task_id: str) -> models.ReviewTask:
    task = session.scalar(select(models.ReviewTask).where(models.ReviewTask.review_task_id == review_task_id))
    if not task:
        raise LookupError(f"Review task not found: {review_task_id}")
    return task


def _get_raw_episode(session: Session, snapshot_id: str, episode_id: str) -> dict[str, Any]:
    row = session.scalar(
        select(models.NegotiationEpisodeRaw).where(
            models.NegotiationEpisodeRaw.snapshot_id == snapshot_id,
            models.NegotiationEpisodeRaw.episode_id == episode_id,
        )
    )
    if not row:
        raise LookupError(f"Episode not found: {episode_id}")
    return row.raw_payload


def _get_latest_edit(session: Session, review_task_id: str) -> models.EpisodeReviewEdit | None:
    return session.scalar(
        select(models.EpisodeReviewEdit)
        .where(models.EpisodeReviewEdit.review_task_id == review_task_id)
        .order_by(models.EpisodeReviewEdit.created_at.desc())
    )


def _add_event(
    session: Session,
    *,
    task: models.ReviewTask,
    actor_user_id: str | None,
    event_type: str,
    note: str | None,
    payload: dict[str, Any] | None = None,
) -> models.ReviewEvent:
    event = models.ReviewEvent(
        review_task_id=task.review_task_id,
        snapshot_id=task.snapshot_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        note=note,
        payload=payload or {},
    )
    session.add(event)
    return event


def claim_review_task(session: Session, review_task_id: str, user: models.User) -> models.ReviewTask:
    task = _get_task(session, review_task_id)
    if task.assigned_user_id and task.assigned_user_id != user.user_id:
        raise PermissionError("Task is already assigned to another user.")

    task.assigned_user_id = user.user_id
    if task.status == "pending":
        task.status = "in_progress"
    task.updated_at = models.utcnow()
    _add_event(
        session,
        task=task,
        actor_user_id=user.user_id,
        event_type="claimed",
        note=f"{user.display_name} 领取了任务。",
    )
    session.commit()
    session.refresh(task)
    return task


def save_review_draft(session: Session, review_task_id: str, user: models.User, data: dict[str, Any]) -> models.ReviewTask:
    task = _get_task(session, review_task_id)
    if task.assigned_user_id and task.assigned_user_id != user.user_id and user.role != "admin":
        raise PermissionError("Task is assigned to another user.")

    task.assigned_user_id = task.assigned_user_id or user.user_id
    raw_episode = _get_raw_episode(session, task.snapshot_id, task.episode_id)
    latest_edit = _get_latest_edit(session, task.review_task_id)

    edit_payload = {
        "workflow_stage": (data.get("workflow_stage") if data.get("workflow_stage") is not None else (latest_edit.workflow_stage if latest_edit else raw_episode.get("workflow_stage"))),
        "episode_goal": (data.get("episode_goal") if data.get("episode_goal") is not None else (latest_edit.episode_goal if latest_edit else raw_episode.get("episode_goal"))),
        "objection_type": (data.get("objection_type") if data.get("objection_type") is not None else (latest_edit.objection_type if latest_edit else raw_episode.get("objection_type"))),
        "creator_traits": (data.get("creator_traits") if data.get("creator_traits") is not None else (latest_edit.creator_traits if latest_edit else raw_episode.get("creator_traits"))),
        "outcome": (data.get("outcome") if data.get("outcome") is not None else (latest_edit.outcome if latest_edit else raw_episode.get("outcome"))),
        "confidence": (data.get("confidence") if data.get("confidence") is not None else (latest_edit.confidence if latest_edit else raw_episode.get("confidence"))),
        "review_notes": (data.get("review_notes") if data.get("review_notes") is not None else (latest_edit.review_notes if latest_edit else raw_episode.get("review_notes"))),
    }

    requested_status = data.get("review_status")
    if requested_status in {"pending", "in_progress", "returned"}:
        task.status = requested_status
    elif task.status == "pending":
        task.status = "in_progress"

    edit = models.EpisodeReviewEdit(
        review_task_id=task.review_task_id,
        snapshot_id=task.snapshot_id,
        episode_id=task.episode_id,
        edited_by_user_id=user.user_id,
        status_at_save=task.status,
        **edit_payload,
    )
    session.add(edit)
    session.flush()

    task.latest_edit_id = edit.edit_id
    task.updated_at = models.utcnow()

    _add_event(
        session,
        task=task,
        actor_user_id=user.user_id,
        event_type="draft_saved",
        note="保存审核草稿。",
        payload={
            "edit_id": edit.edit_id,
            "status": task.status,
        },
    )
    session.commit()
    session.refresh(task)
    return task


def submit_review_task(session: Session, review_task_id: str, user: models.User, review_notes: str | None) -> models.ReviewTask:
    task = _get_task(session, review_task_id)
    if task.assigned_user_id and task.assigned_user_id != user.user_id and user.role != "admin":
        raise PermissionError("Task is assigned to another user.")

    task.assigned_user_id = task.assigned_user_id or user.user_id
    latest_edit = _get_latest_edit(session, task.review_task_id)
    if review_notes and latest_edit:
        latest_edit.review_notes = review_notes

    task.status = "submitted"
    task.submitted_at = models.utcnow()
    task.updated_at = models.utcnow()
    _add_event(
        session,
        task=task,
        actor_user_id=user.user_id,
        event_type="submitted",
        note=review_notes or "提交审核。",
        payload={"latest_edit_id": task.latest_edit_id},
    )
    session.commit()
    session.refresh(task)
    return task


def approve_review_task(session: Session, review_task_id: str, user: models.User, review_notes: str | None) -> models.ReviewTask:
    task = _get_task(session, review_task_id)
    task.status = "approved"
    task.approved_at = models.utcnow()
    task.approved_by_user_id = user.user_id
    task.updated_at = models.utcnow()
    _add_event(
        session,
        task=task,
        actor_user_id=user.user_id,
        event_type="approved",
        note=review_notes or "审核通过。",
        payload={"latest_edit_id": task.latest_edit_id},
    )
    session.commit()
    session.refresh(task)
    return task


def return_review_task(session: Session, review_task_id: str, user: models.User, review_notes: str | None) -> models.ReviewTask:
    task = _get_task(session, review_task_id)
    task.status = "returned"
    task.returned_at = models.utcnow()
    task.updated_at = models.utcnow()
    _add_event(
        session,
        task=task,
        actor_user_id=user.user_id,
        event_type="returned",
        note=review_notes or "审核退回。",
        payload={"latest_edit_id": task.latest_edit_id},
    )
    session.commit()
    session.refresh(task)
    return task


def build_mutation_payload(session: Session, task: models.ReviewTask) -> dict[str, Any]:
    detail = get_review_task_detail(session, task.review_task_id)
    return {
        "task": detail["task"],
        "latest_edit": detail["latest_edit"],
        "events": detail["events"],
    }
