from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models import User


def seed_local_users(session: Session, settings: Settings) -> None:
    existing = {
        user.username: user
        for user in session.scalars(select(User)).all()
    }

    created = False
    for config in settings.local_users:
        user = existing.get(config.username)
        if user:
            user.display_name = config.display_name
            user.role = config.role
            user.is_active = True
            if not user.password_hash:
                user.password_hash = hash_password(config.password)
            continue

        session.add(
            User(
                username=config.username,
                display_name=config.display_name,
                role=config.role,
                password_hash=hash_password(config.password),
                is_active=True,
            )
        )
        created = True

    if created:
        session.flush()
