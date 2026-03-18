from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.asset import Asset, AssetKind, AssetOwnerType, AssetReviewState, AssetSource
from app.models.user import User, UserRole
from app.services.auth_security import create_session_and_tokens

DEFAULT_PASSWORD = "VeryStrong!Pass123"


def create_user(
    db: Session,
    *,
    username: str,
    role: UserRole = UserRole.admin,
    password: str = DEFAULT_PASSWORD,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
        needs_password_setup=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_asset(
    db: Session,
    *,
    owner_type: AssetOwnerType,
    owner_id: uuid.UUID,
    review_state: AssetReviewState = AssetReviewState.approved,
    kind: AssetKind = AssetKind.image,
    hash_value: str | None = None,
) -> Asset:
    asset = Asset(
        owner_type=owner_type,
        owner_id=owner_id,
        kind=kind,
        source=AssetSource.upload,
        local_path=None,
        title="asset",
        source_name="upload",
        size_bytes=123,
        hash=hash_value,
        review_state=review_state,
        is_primary=False,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def create_tokens_for_user(db: Session, *, user: User) -> tuple[str, str]:
    session, access_token, refresh_token, _, _ = create_session_and_tokens(
        db,
        user=user,
        ip_address="127.0.0.1",
        user_agent="pytest",
        mfa_verified=False,
    )
    session.expires_at = datetime.utcnow() + timedelta(
        minutes=settings.SESSION_ABSOLUTE_TIMEOUT_MINUTES
    )
    session.idle_expires_at = datetime.utcnow() + timedelta(
        minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES
    )
    db.commit()
    return access_token, refresh_token


def login(client: TestClient, *, username: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    csrf_token = client.cookies.get(settings.CSRF_COOKIE_NAME)
    return {
        "response": response,
        "csrf": csrf_token,
        "access_cookie": client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME),
        "refresh_cookie": client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME),
    }
