from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_session, get_settings_from_app
from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserInfo
from app.services.assets import serialize_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_from_app),
):
    user = session.scalar(select(User).where(User.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    token = create_access_token(
        {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
        },
        settings.secret_key,
        settings.access_token_ttl_seconds,
    )
    return LoginResponse(
        access_token=token,
        user=serialize_user(user),
    )


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)) -> UserInfo:
    return serialize_user(current_user)
