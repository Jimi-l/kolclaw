from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session, require_roles
from app.models import Snapshot, User
from app.schemas import SnapshotResponse
from app.services.assets import list_snapshots, serialize_snapshot

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("", response_model=list[SnapshotResponse])
def get_snapshots(
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[SnapshotResponse]:
    return [serialize_snapshot(snapshot) for snapshot in list_snapshots(session)]


@router.post("/{snapshot_id}/activate", response_model=SnapshotResponse)
def activate_snapshot(
    snapshot_id: str,
    _current_user: User = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> SnapshotResponse:
    snapshot = session.scalar(select(Snapshot).where(Snapshot.snapshot_id == snapshot_id))
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found.")

    session.execute(update(Snapshot).values(is_active=False))
    snapshot.is_active = True
    session.commit()
    session.refresh(snapshot)
    return serialize_snapshot(snapshot)
