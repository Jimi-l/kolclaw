from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session, get_settings_from_app
from app.core.config import Settings
from app.models import User
from app.schemas import DashboardSummaryResponse
from app.services.assets import build_dashboard_summary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    _current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_from_app),
) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(**build_dashboard_summary(session, settings.default_snapshot_dir))
