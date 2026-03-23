from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.authorization import Permission, has_permission
from app.core.config import settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.auth_session import AuthSession
from app.models.user import User, UserRole
from app.services.auth_security import is_token_revoked, revoke_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


@dataclass
class AuthContext:
    user: User
    session: AuthSession
    payload: dict


@dataclass
class SensitiveActionContext:
    action: str
    confirmation_required: bool
    confirmation_provided: bool
    step_up_required: bool
    step_up_satisfied: bool
    request_id: str | None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if settings.TRUST_PROXY_HEADERS and xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _touch_session_if_needed(db: Session, session: AuthSession) -> None:
    now = _utcnow()
    if (now - session.last_activity_at) < timedelta(seconds=30):
        return
    session.last_activity_at = now
    session.idle_expires_at = now + timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)
    db.commit()


def get_current_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> AuthContext:
    token_value = (
        token
        or request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
        or request.cookies.get(settings.AUTH_COOKIE_NAME)
    )
    if not token_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(token_value)
        username = payload.get("sub")
        token_type = payload.get("typ")
        sid = payload.get("sid")
        jti = payload.get("jti")
        if not username:
            raise ValueError("missing sub")
        if token_type != "access":
            raise ValueError("invalid token type")
        if not sid or not jti:
            raise ValueError("missing session claims")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if is_token_revoked(db, jti=jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found"
        )

    try:
        session_id = uuid.UUID(str(sid))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session = (
        db.query(AuthSession)
        .filter(AuthSession.id == session_id, AuthSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")

    now = _utcnow()
    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    if session.expires_at <= now:
        revoke_session(db, session=session, reason="absolute_timeout")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if session.idle_expires_at <= now:
        revoke_session(db, session=session, reason="idle_timeout")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    _touch_session_if_needed(db, session)
    return AuthContext(user=user, session=session, payload=payload)


def get_current_user(context: AuthContext = Depends(get_current_auth_context)) -> User:
    return context.user


def get_current_auth_session(
    context: AuthContext = Depends(get_current_auth_context),
) -> AuthSession:
    return context.session


def require_role(*roles: UserRole):
    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dep


def require_permission(permission: Permission):
    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dep


def require_permissions_any(*permissions: Permission):
    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not any(has_permission(current_user, permission) for permission in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return _dep


def require_sensitive_action(action: str):
    def _dep(
        request: Request,
        context: AuthContext = Depends(get_current_auth_context),
    ) -> SensitiveActionContext:
        confirmation_required = settings.SECURITY_SENSITIVE_ACTION_CONFIRMATION_REQUIRED
        header_name = settings.SECURITY_SENSITIVE_ACTION_CONFIRMATION_HEADER.strip().lower()
        expected_value = settings.SECURITY_SENSITIVE_ACTION_CONFIRMATION_VALUE
        header_value = request.headers.get(header_name)
        confirmation_provided = bool(header_value) and header_value == expected_value

        if confirmation_required and not confirmation_provided:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail="Sensitive action confirmation required",
            )

        step_up_required = settings.SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA
        step_up_satisfied = bool(context.session.mfa_verified)
        if step_up_required and not step_up_satisfied:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Step-up authentication required",
            )

        return SensitiveActionContext(
            action=action,
            confirmation_required=confirmation_required,
            confirmation_provided=confirmation_provided,
            step_up_required=step_up_required,
            step_up_satisfied=step_up_satisfied,
            request_id=request.headers.get("x-request-id"),
        )

    return _dep
