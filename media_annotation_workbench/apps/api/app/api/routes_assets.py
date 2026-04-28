from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import AssetDetailResponse, AssetListResponse
from app.services.assets import FILTERABLE_FIELDS, get_asset_detail, list_asset_items
from app.services.asset_registry import DATA_ASSETS, DOC_ASSETS
from app.services.display_labels import ASSET_TYPE_LABELS

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{asset_type}", response_model=AssetListResponse)
def list_assets(
    asset_type: str,
    snapshot_id: str | None = None,
    view: str = Query(default="reviewed", pattern="^(raw|reviewed)$"),
    search: str | None = None,
    workflow_stage: str | None = None,
    episode_goal: str | None = None,
    objection_type: str | None = None,
    creator_id: str | None = None,
    knowledge_base: str | None = None,
    review_status: str | None = None,
    conversation_id: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    offset: int = 0,
    limit: int = 50,
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AssetListResponse:
    if asset_type in DOC_ASSETS:
        raise HTTPException(status_code=400, detail="Document assets are available via /api/docs or /api/assets/{type}/{id}.")
    if asset_type not in DATA_ASSETS:
        raise HTTPException(status_code=404, detail="Unknown asset type.")

    filter_values = {
        "workflow_stage": workflow_stage,
        "episode_goal": episode_goal,
        "objection_type": objection_type,
        "creator_id": creator_id,
        "knowledge_base": knowledge_base,
        "review_status": review_status,
        "conversation_id": conversation_id,
        "priority": priority,
        "status": status,
    }
    filters = {field: value for field, value in filter_values.items() if field in FILTERABLE_FIELDS and value is not None}
    try:
        resolved_snapshot_id, items, total = list_asset_items(
            session,
            asset_type,
            snapshot_id=snapshot_id,
            view=view,
            search=search,
            filters=filters,
            sort_by=sort_by,
            sort_dir=sort_dir,
            offset=offset,
            limit=limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AssetListResponse(
        asset_type=asset_type,
        asset_type_label=ASSET_TYPE_LABELS.get(asset_type, asset_type),
        snapshot_id=resolved_snapshot_id,
        view=view,
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )


@router.get("/{asset_type}/{item_id}", response_model=AssetDetailResponse)
def get_asset(
    asset_type: str,
    item_id: str,
    snapshot_id: str | None = None,
    view: str = Query(default="reviewed", pattern="^(raw|reviewed)$"),
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AssetDetailResponse:
    if asset_type not in DATA_ASSETS and asset_type not in DOC_ASSETS:
        raise HTTPException(status_code=404, detail="Unknown asset type.")
    try:
        resolved_snapshot_id, raw_item, reviewed_item, review_status, related, document_content, document_format = get_asset_detail(
            session,
            asset_type,
            item_id,
            snapshot_id=snapshot_id,
            view=view,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AssetDetailResponse(
        asset_type=asset_type,
        asset_type_label=ASSET_TYPE_LABELS.get(asset_type, asset_type),
        snapshot_id=resolved_snapshot_id,
        view=view,
        raw_item=raw_item,
        reviewed_item=reviewed_item,
        review_status=review_status,
        related=related,
        document_content=document_content,
        document_format=document_format,
    )
