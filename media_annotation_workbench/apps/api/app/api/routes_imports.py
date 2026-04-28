from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session, require_roles
from app.models import User
from app.schemas import ImportRequest, ImportResponse
from app.services.assets import serialize_snapshot
from app.services.importer import import_snapshot

router = APIRouter(prefix="/api/imports", tags=["imports"])


@router.post("", response_model=ImportResponse)
def import_snapshot_route(
    payload: ImportRequest,
    _current_user: User = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ImportResponse:
    try:
        snapshot = import_snapshot(session, payload.source_dir, activate=payload.activate)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportResponse(snapshot=serialize_snapshot(snapshot), imported_assets=snapshot.asset_counts or {})
