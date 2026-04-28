from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import DocumentResponse
from app.services.assets import get_document

router = APIRouter(prefix="/api/docs", tags=["docs"])


@router.get("/{doc_type}", response_model=DocumentResponse)
def get_doc(
    doc_type: str,
    snapshot_id: str | None = None,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DocumentResponse:
    try:
        resolved_snapshot_id, content, format_name = get_document(session, doc_type, snapshot_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentResponse(
        snapshot_id=resolved_snapshot_id,
        doc_type=doc_type,
        content=content,
        format=format_name,
    )
