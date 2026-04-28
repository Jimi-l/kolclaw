from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import ReviewedEpisodesExportResponse
from app.services.assets import list_reviewed_episodes

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.get("/reviewed-episodes", response_model=ReviewedEpisodesExportResponse)
def export_reviewed_episodes(
    snapshot_id: str | None = None,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewedEpisodesExportResponse:
    try:
        resolved_snapshot_id, items = list_reviewed_episodes(session, snapshot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewedEpisodesExportResponse(snapshot_id=resolved_snapshot_id, total=len(items), items=items)
