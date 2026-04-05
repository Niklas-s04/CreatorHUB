from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext,
    SensitiveActionContext,
    get_client_ip,
    get_current_auth_context,
    get_current_user,
    get_db,
    require_permission,
    require_sensitive_action,
)
from app.core.authorization import Permission, permission_values_for_role
from app.core.config import settings
from app.core.security import (
    create_csrf_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.auth_session import AuthSession, LoginHistory, PasswordResetToken
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.auth import (
    AdminBootstrapStatusOut,
    AdminPasswordSetupIn,
    AdminSessionOut,
    ChangePasswordIn,
    LoginHistoryOut,
    MfaDisableIn,
    MfaEnableIn,
    MfaEnableOut,
    MfaProvisionOut,
    MfaStatusOut,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    PasswordResetRequestOut,
    RegisterRequestIn,
    RegisterRequestOut,
    SessionOut,
    TokenOut,
)
from app.schemas.user import UserCreate, UserOut
from app.services.audit import record_audit_log
from app.services.auth_security import (
    create_session_and_tokens,
    create_totp_secret,
    generate_recovery_codes,
    hash_recovery_codes,
    is_suspicious_login,
    is_token_revoked,
    record_login_attempt,
    revoke_session,
    revoke_token,
    rotate_refresh_token,
    totp_uri,
    verify_recovery_code,
    verify_totp_code,
)
from app.services.bootstrap import (
    assert_valid_bootstrap_token,
    finalize_bootstrap,
)
from app.services.domain_events import emit_domain_event
from app.services.domain_rules import validate_registration_status_change
from app.services.errors import BusinessRuleViolation

router = APIRouter()
user_router = APIRouter()
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")


def _validate_username(username: str) -> str:
    candidate = username.strip()
    if not USERNAME_RE.match(candidate):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-64 chars and only contain letters, numbers, . _ -",
        )
    return candidate


def _validate_password_strength(password: str) -> str:
    candidate = password.strip()
    if len(candidate) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    checks = [
        any(c.islower() for c in candidate),
        any(c.isupper() for c in candidate),
        any(c.isdigit() for c in candidate),
        any(not c.isalnum() for c in candidate),
    ]
    if not all(checks):
        raise HTTPException(
            status_code=400,
            detail="Password must include upper/lowercase letters, a number, and a special character",
        )
    return candidate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_user_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > _utcnow())


def _user_summary(
    user: User,
    *,
    active_sessions: int = 0,
    last_activity_at: datetime | None = None,
) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        needs_password_setup=user.needs_password_setup,
        mfa_enabled=user.mfa_enabled,
        locked_until=user.locked_until,
        last_activity_at=last_activity_at,
        active_sessions=active_sessions,
        permissions=permission_values_for_role(user.role),
    )


def _serialize_registration_request(
    req: RegistrationRequest, reviewer_name: str | None = None
) -> RegisterRequestOut:
    return RegisterRequestOut(
        id=req.id,
        username=req.username,
        status=req.status,
        reviewed_at=req.reviewed_at,
        reviewed_by_user_id=req.reviewed_by_user_id,
        reviewed_by_username=reviewer_name,
        rejection_reason=req.rejection_reason,
    )


def _safe_exp_from_payload(payload: dict) -> datetime:
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    return _utcnow() + timedelta(minutes=settings.JWT_REFRESH_EXPIRE_MINUTES)


def _apply_failed_login(user: User) -> None:
    user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= settings.AUTH_MAX_FAILED_ATTEMPTS:
        user.locked_until = _utcnow() + timedelta(minutes=settings.AUTH_LOCK_MINUTES)


def _cookie_lifetime_seconds(*, session: AuthSession) -> tuple[int, int, int]:
    now = _utcnow()
    absolute_remaining = max(0, int((session.expires_at - now).total_seconds()))
    idle_remaining = max(0, int((session.idle_expires_at - now).total_seconds()))

    access_max_age = max(
        1, min(settings.AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS, absolute_remaining, idle_remaining)
    )
    refresh_max_age = max(1, min(settings.AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS, absolute_remaining))
    csrf_max_age = access_max_age
    return access_max_age, refresh_max_age, csrf_max_age


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str, session: AuthSession
) -> None:
    access_max_age, refresh_max_age, csrf_max_age = _cookie_lifetime_seconds(session=session)
    domain = settings.AUTH_COOKIE_DOMAIN

    response.set_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=access_max_age,
        path="/api",
        domain=domain,
    )
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path="/api/auth",
        domain=domain,
    )
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=access_max_age,
        path="/api",
        domain=domain,
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=create_csrf_token(str(session.id)),
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=csrf_max_age,
        path="/",
        domain=domain,
    )


def _clear_auth_cookies(response: Response) -> None:
    domain = settings.AUTH_COOKIE_DOMAIN
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE_NAME, path="/api", domain=domain)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/api/auth", domain=domain)
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/api", domain=domain)
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/", domain=domain)


def _set_post_logout_csrf_cookie(response: Response) -> None:
    domain = settings.AUTH_COOKIE_DOMAIN
    anonymous_session_id = str(uuid.uuid4())
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=create_csrf_token(anonymous_session_id),
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=max(60, min(3600, settings.AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS)),
        path="/",
        domain=domain,
    )


def _verify_mfa(user: User, code: str) -> bool:
    if not user.mfa_enabled:
        return True

    if user.mfa_secret and verify_totp_code(user.mfa_secret, code):
        return True

    ok, remaining = verify_recovery_code(user.mfa_recovery_codes, code)
    if ok:
        user.mfa_recovery_codes = remaining
        return True
    return False


@router.post("/token", response_model=TokenOut)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    otp: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> TokenOut:
    username = form_data.username.strip()
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user = db.query(User).filter(User.username == username).first()

    if user and user.role == UserRole.admin and user.needs_password_setup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin password setup required"
        )

    if user and not user.is_active:
        suspicious = is_suspicious_login(
            db, user=user, ip_address=ip_address, user_agent=user_agent, success=False
        )
        record_login_attempt(
            db,
            user=user,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            suspicious=suspicious,
            reason="inactive",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    if user and user.locked_until and user.locked_until > _utcnow():
        suspicious = is_suspicious_login(
            db, user=user, ip_address=ip_address, user_agent=user_agent, success=False
        )
        record_login_attempt(
            db,
            user=user,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            suspicious=suspicious,
            reason="locked",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked"
        )

    if not user or not verify_password(form_data.password, user.hashed_password):
        suspicious = is_suspicious_login(
            db, user=user, ip_address=ip_address, user_agent=user_agent, success=False
        )
        if user:
            _apply_failed_login(user)
        record_login_attempt(
            db,
            user=user,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            suspicious=suspicious,
            reason="invalid_credentials",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    if user.mfa_enabled:
        if not otp or not _verify_mfa(user, otp):
            _apply_failed_login(user)
            suspicious = is_suspicious_login(
                db, user=user, ip_address=ip_address, user_agent=user_agent, success=False
            )
            record_login_attempt(
                db,
                user=user,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                suspicious=suspicious,
                reason="mfa_failed",
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA required or invalid"
            )

    user.failed_login_attempts = 0
    user.locked_until = None
    suspicious = is_suspicious_login(
        db, user=user, ip_address=ip_address, user_agent=user_agent, success=True
    )
    record_login_attempt(
        db,
        user=user,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        success=True,
        suspicious=suspicious,
        reason=None,
    )

    session, access_token, refresh_token, _, _ = create_session_and_tokens(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        mfa_verified=bool(user.mfa_enabled),
    )
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token, session)
    return TokenOut(access_token=access_token)


@router.get("/bootstrap-status", response_model=AdminBootstrapStatusOut)
def bootstrap_status(
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> AdminBootstrapStatusOut:
    assert_valid_bootstrap_token(db, bootstrap_token)
    admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
    if not admin:
        return AdminBootstrapStatusOut(
            admin_username=settings.BOOTSTRAP_ADMIN_USERNAME, needs_password_setup=True
        )
    return AdminBootstrapStatusOut(
        admin_username=admin.username,
        needs_password_setup=bool(admin.needs_password_setup),
    )


@router.post("/setup-admin-password", response_model=TokenOut)
def setup_admin_password(
    request: Request,
    response: Response,
    payload: AdminPasswordSetupIn,
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> TokenOut:
    bootstrap_state = assert_valid_bootstrap_token(db, bootstrap_token)
    password = _validate_password_strength(payload.password)

    admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")
    if not admin.needs_password_setup:
        raise HTTPException(status_code=409, detail="Admin password already set")

    admin.hashed_password = hash_password(password)
    admin.needs_password_setup = False
    admin.is_active = True
    admin.password_changed_at = _utcnow()
    finalize_bootstrap(bootstrap_state, completed_by=admin.username)

    record_audit_log(
        db,
        actor=admin,
        action="initial_admin_setup_completed",
        entity_type="bootstrap",
        entity_id=str(bootstrap_state.id),
        description="Initial admin setup completed and bootstrap disabled",
        metadata={
            "ip": get_client_ip(request),
            "user_agent": (request.headers.get("user-agent") or "")[:512] or None,
            "bootstrap_completed_at": bootstrap_state.setup_completed_at.isoformat()
            if bootstrap_state.setup_completed_at
            else None,
        },
    )

    session, access_token, refresh_token, _, _ = create_session_and_tokens(
        db,
        user=admin,
        ip_address=None,
        user_agent=None,
        mfa_verified=False,
    )
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token, session)
    return TokenOut(access_token=access_token)


@router.post("/refresh", response_model=TokenOut)
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    token_value = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    try:
        payload = decode_token(token_value)
        if payload.get("typ") != "refresh":
            raise ValueError("invalid type")
        sid = payload.get("sid")
        jti = payload.get("jti")
        username = payload.get("sub")
        if not sid or not jti or not username:
            raise ValueError("invalid claims")
    except Exception:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    if is_token_revoked(db, jti=jti):
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found"
        )
    if _is_user_locked(user):
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked"
        )

    try:
        session_id = uuid.UUID(str(sid))
    except Exception:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session = (
        db.query(AuthSession)
        .filter(AuthSession.id == session_id, AuthSession.user_id == user.id)
        .first()
    )
    if not session or session.revoked_at is not None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")

    now = _utcnow()
    if session.expires_at <= now or session.idle_expires_at <= now:
        revoke_session(db, session=session, reason="session_timeout")
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if session.refresh_jti != jti or session.refresh_token_hash != hash_token(token_value):
        revoke_session(db, session=session, reason="refresh_reuse_detected")
        db.commit()
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid"
        )

    access_token, refresh_token_value, _, _ = rotate_refresh_token(db, user=user, session=session)
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, session)
    return TokenOut(access_token=access_token)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    token_values = [
        request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME),
        request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME),
        request.cookies.get(settings.AUTH_COOKIE_NAME),
    ]
    session_ids: set[uuid.UUID] = set()
    revoked_jtis: set[str] = set()
    for token_value in [t for t in token_values if t]:
        try:
            payload = decode_token(token_value)
            jti = payload.get("jti")
            sid = payload.get("sid")
            if jti and jti not in revoked_jtis:
                revoke_token(db, jti=jti, expires_at=_safe_exp_from_payload(payload))
                revoked_jtis.add(jti)
            if sid:
                session_ids.add(uuid.UUID(str(sid)))
        except Exception:
            continue

    if session_ids:
        sessions = db.query(AuthSession).filter(AuthSession.id.in_(list(session_ids))).all()
        for session in sessions:
            revoke_session(db, session=session, reason="logout")
    db.commit()

    _clear_auth_cookies(response)
    _set_post_logout_csrf_cookie(response)
    return {"ok": "true"}


@user_router.delete("/user/account")
@router.delete("/account")
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    sensitive_action: SensitiveActionContext = Depends(require_sensitive_action("delete_account")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Request account deletion for the current user.
    Schedules account for deletion after 30-day grace period.
    Requires sensitive action confirmation (MFA step-up if enabled).
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already inactive",
        )

    if current_user.deletion_requested_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account deletion already requested",
        )

    # Soft-delete: mark for deletion and deactivate
    current_user.is_active = False
    current_user.deletion_requested_at = _utcnow()
    db.add(current_user)

    # Revoke all active sessions
    active_sessions = (
        db.query(AuthSession)
        .filter(
            AuthSession.user_id == current_user.id,
            AuthSession.revoked_at.is_(None),
        )
        .all()
    )
    for session in active_sessions:
        revoke_session(db, session=session, reason="account_deletion_requested")

    # Create audit log
    record_audit_log(
        db=db,
        actor=current_user,
        action="auth.user.deletion_requested",
        entity_type="User",
        entity_id=str(current_user.id),
        description=f"User {current_user.username} requested account deletion. Account will be permanently purged after 30 days.",
        metadata={
            "request_id": sensitive_action.request_id,
            "mfa_verified": sensitive_action.step_up_satisfied,
            "confirmation_provided": sensitive_action.confirmation_provided,
        },
    )

    db.commit()

    # Clear auth cookies
    _clear_auth_cookies(response)

    return {
        "ok": "true",
        "message": "Account scheduled for deletion. Permanent removal will occur after 30 days.",
    }


@router.post("/register-request", response_model=RegisterRequestOut)
def register_request(
    payload: RegisterRequestIn, db: Session = Depends(get_db)
) -> RegisterRequestOut:
    username = _validate_username(payload.username)
    password = _validate_password_strength(payload.password)

    if username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Username is reserved")

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    existing_request = (
        db.query(RegistrationRequest).filter(RegistrationRequest.username == username).first()
    )
    if existing_request:
        if existing_request.status == RegistrationRequestStatus.pending:
            raise HTTPException(status_code=400, detail="Registration request already pending")
        try:
            validate_registration_status_change(
                current_status=existing_request.status,
                target_status=RegistrationRequestStatus.pending,
            )
        except BusinessRuleViolation as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        existing_request.hashed_password = hash_password(password)
        before_status = existing_request.status
        existing_request.status = RegistrationRequestStatus.pending
        existing_request.reviewed_by_user_id = None
        existing_request.reviewed_at = None
        existing_request.rejection_reason = None
        emit_domain_event(
            db,
            actor=None,
            event_name="registration.request.reopened",
            entity_type="registration_request",
            entity_id=str(existing_request.id),
            payload={
                "from": before_status.value,
                "to": existing_request.status.value,
                "username": existing_request.username,
            },
            description="Registration request reopened by a new submission",
        )
        db.commit()
        db.refresh(existing_request)
        return existing_request

    request = RegistrationRequest(
        username=username,
        hashed_password=hash_password(password),
        status=RegistrationRequestStatus.pending,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    active_sessions = (
        db.query(AuthSession)
        .filter(
            AuthSession.user_id == current_user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > _utcnow(),
        )
        .count()
    )
    return _user_summary(current_user, active_sessions=active_sessions)


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_manage)),
) -> UserOut:
    username = _validate_username(payload.username)
    password = _validate_password_strength(payload.password)

    if (
        username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower()
        or payload.role == UserRole.admin
    ):
        raise HTTPException(status_code=400, detail="Admin account is managed separately")
    exists = db.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=payload.role,
        needs_password_setup=False,
        password_changed_at=_utcnow(),
    )
    db.add(user)
    db.flush()
    record_audit_log(
        db,
        actor=admin,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Created user '{user.username}'",
        after={
            "username": user.username,
            "role": user.role.value,
            "is_active": user.is_active,
        },
        metadata={
            "audit_category": "permission_change",
            "critical": True,
        },
    )
    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db), _: User = Depends(require_permission(Permission.user_read))
) -> list[UserOut]:
    now = _utcnow()
    users = db.query(User).order_by(User.created_at.desc()).all()
    user_ids = [u.id for u in users]
    active_session_counts: dict[uuid.UUID, int] = {}
    session_activity: dict[uuid.UUID, datetime | None] = {}
    login_activity: dict[uuid.UUID, datetime | None] = {}

    if user_ids:
        session_rows = (
            db.query(
                AuthSession.user_id,
                func.count(AuthSession.id),
                func.max(AuthSession.last_activity_at),
            )
            .filter(
                AuthSession.user_id.in_(user_ids),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .group_by(AuthSession.user_id)
            .all()
        )
        for user_id, active_sessions, last_session_activity in session_rows:
            active_session_counts[user_id] = int(active_sessions or 0)
            session_activity[user_id] = last_session_activity

        login_rows = (
            db.query(LoginHistory.user_id, func.max(LoginHistory.occurred_at))
            .filter(LoginHistory.user_id.in_(user_ids), LoginHistory.success.is_(True))
            .group_by(LoginHistory.user_id)
            .all()
        )
        for user_id, last_login_at in login_rows:
            login_activity[user_id] = last_login_at

    summaries: list[UserOut] = []
    for user in users:
        last_activity_at = session_activity.get(user.id)
        last_login_at = login_activity.get(user.id)
        if last_login_at and (last_activity_at is None or last_login_at > last_activity_at):
            last_activity_at = last_login_at
        summaries.append(
            _user_summary(
                user,
                active_sessions=active_session_counts.get(user.id, 0),
                last_activity_at=last_activity_at,
            )
        )
    return summaries


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    role: UserRole | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_manage)),
    sensitive_action: SensitiveActionContext = Depends(
        require_sensitive_action("user.role_or_status.update")
    ),
) -> UserOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Admin account is managed separately")
    if user.id == admin.id and (role is not None or is_active is not None):
        raise HTTPException(
            status_code=400,
            detail="Self role/status changes are not allowed for security reasons",
        )

    before = {
        "role": user.role.value,
        "is_active": user.is_active,
    }
    if role is not None:
        if role == UserRole.admin:
            raise HTTPException(
                status_code=400, detail="Only the bootstrap admin account can be admin"
            )
        user.role = role
    if is_active is not None:
        user.is_active = is_active

    after = {
        "role": user.role.value,
        "is_active": user.is_active,
    }
    if before != after:
        record_audit_log(
            db,
            actor=admin,
            action="user.role_or_status.update",
            entity_type="user",
            entity_id=str(user.id),
            description=f"Updated role/status for user '{user.username}'",
            before=before,
            after=after,
            metadata={
                "audit_category": "permission_change",
                "critical": True,
                "permissions_before": permission_values_for_role(UserRole(before["role"])),
                "permissions_after": permission_values_for_role(user.role),
                "sensitive_action": sensitive_action.action,
                "confirmation_required": sensitive_action.confirmation_required,
                "confirmation_provided": sensitive_action.confirmation_provided,
                "step_up_required": sensitive_action.step_up_required,
                "step_up_satisfied": sensitive_action.step_up_satisfied,
                "request_id": sensitive_action.request_id,
            },
        )

    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.get("/users/{user_id}/sessions", response_model=list[AdminSessionOut])
def list_user_sessions(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_current_auth_context),
    _: User = Depends(require_permission(Permission.user_read)),
) -> list[AdminSessionOut]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id)
        .order_by(AuthSession.last_activity_at.desc(), AuthSession.created_at.desc())
        .all()
    )

    return [
        AdminSessionOut(
            id=session.id,
            created_at=session.created_at,
            last_activity_at=session.last_activity_at,
            expires_at=session.expires_at,
            idle_expires_at=session.idle_expires_at,
            ip_address=session.ip_address,
            device_label=session.device_label,
            user_agent=session.user_agent,
            mfa_verified=session.mfa_verified,
            is_current=bool(context.user.id == user.id and session.id == context.session.id),
            revoked_at=session.revoked_at,
            revoked_reason=session.revoked_reason,
        )
        for session in sessions
    ]


@router.post("/users/{user_id}/password-reset", response_model=PasswordResetRequestOut)
def admin_request_password_reset(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_manage)),
    sensitive_action: SensitiveActionContext = Depends(
        require_sensitive_action("user.password.reset")
    ),
) -> PasswordResetRequestOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Admin account is managed separately")

    now = _utcnow()
    before_locked_until = user.locked_until.isoformat() if user.locked_until else None
    before_failed_attempts = int(user.failed_login_attempts or 0)
    previous_tokens = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .all()
    )
    for token in previous_tokens:
        token.used_at = now

    reset_token = secrets.token_urlsafe(32)
    reset_entry = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(reset_token),
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
        requested_ip=get_client_ip(request),
        requested_user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )
    db.add(reset_entry)

    revoked_sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for session in revoked_sessions:
        revoke_session(db, session=session, reason="admin_password_reset")

    user.failed_login_attempts = 0
    user.locked_until = None

    record_audit_log(
        db,
        actor=admin,
        action="user.password.reset.request",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Generated password reset token for user '{user.username}'",
        before={
            "locked_until": before_locked_until,
            "failed_login_attempts": before_failed_attempts,
        },
        after={
            "reset_token_issued": True,
            "reset_token_expires_at": reset_entry.expires_at.isoformat(),
            "revoked_sessions": len(revoked_sessions),
        },
        metadata={
            "audit_category": "security",
            "critical": True,
            "sensitive_action": sensitive_action.action,
            "confirmation_required": sensitive_action.confirmation_required,
            "confirmation_provided": sensitive_action.confirmation_provided,
            "step_up_required": sensitive_action.step_up_required,
            "step_up_satisfied": sensitive_action.step_up_satisfied,
            "request_id": sensitive_action.request_id,
        },
    )

    db.commit()
    return PasswordResetRequestOut(ok=True, reset_token=reset_token)


@router.post("/users/{user_id}/lock", response_model=UserOut)
def lock_user(
    user_id: uuid.UUID,
    request: Request,
    minutes: int = Query(default=settings.AUTH_LOCK_MINUTES, ge=1, le=10080),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_manage)),
    sensitive_action: SensitiveActionContext = Depends(require_sensitive_action("user.lock")),
) -> UserOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Admin account is managed separately")

    before = {
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "failed_login_attempts": int(user.failed_login_attempts or 0),
    }
    user.locked_until = _utcnow() + timedelta(minutes=minutes)
    user.failed_login_attempts = max(
        int(user.failed_login_attempts or 0), settings.AUTH_MAX_FAILED_ATTEMPTS
    )

    revoked_sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for session in revoked_sessions:
        revoke_session(db, session=session, reason="admin_lock")

    after = {
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "failed_login_attempts": int(user.failed_login_attempts or 0),
        "revoked_sessions": len(revoked_sessions),
    }
    record_audit_log(
        db,
        actor=admin,
        action="user.lock",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Locked user '{user.username}'",
        before=before,
        after=after,
        metadata={
            "audit_category": "security",
            "critical": True,
            "minutes": minutes,
            "sensitive_action": sensitive_action.action,
            "confirmation_required": sensitive_action.confirmation_required,
            "confirmation_provided": sensitive_action.confirmation_provided,
            "step_up_required": sensitive_action.step_up_required,
            "step_up_satisfied": sensitive_action.step_up_satisfied,
            "request_id": sensitive_action.request_id,
        },
    )

    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.post("/users/{user_id}/unlock", response_model=UserOut)
def unlock_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_manage)),
    sensitive_action: SensitiveActionContext = Depends(require_sensitive_action("user.unlock")),
) -> UserOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Admin account is managed separately")

    before = {
        "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        "failed_login_attempts": int(user.failed_login_attempts or 0),
    }
    user.locked_until = None
    user.failed_login_attempts = 0

    record_audit_log(
        db,
        actor=admin,
        action="user.unlock",
        entity_type="user",
        entity_id=str(user.id),
        description=f"Unlocked user '{user.username}'",
        before=before,
        after={"locked_until": None, "failed_login_attempts": 0},
        metadata={
            "audit_category": "security",
            "critical": True,
            "sensitive_action": sensitive_action.action,
            "confirmation_required": sensitive_action.confirmation_required,
            "confirmation_provided": sensitive_action.confirmation_provided,
            "step_up_required": sensitive_action.step_up_required,
            "step_up_satisfied": sensitive_action.step_up_satisfied,
            "request_id": sensitive_action.request_id,
        },
    )

    db.commit()
    db.refresh(user)
    return _user_summary(user)


@router.get("/registration-requests", response_model=list[RegisterRequestOut])
def list_registration_requests(
    status_filter: RegistrationRequestStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.user_approve_registration)),
) -> list[RegisterRequestOut]:
    query = db.query(RegistrationRequest)
    if status_filter is not None:
        query = query.filter(RegistrationRequest.status == status_filter)
    requests = query.order_by(RegistrationRequest.created_at.desc()).all()
    reviewer_ids = {req.reviewed_by_user_id for req in requests if req.reviewed_by_user_id}
    reviewer_names: dict[uuid.UUID, str] = {}
    if reviewer_ids:
        for reviewer in db.query(User).filter(User.id.in_(reviewer_ids)).all():
            reviewer_names[reviewer.id] = reviewer.username
    return [
        _serialize_registration_request(req, reviewer_names.get(req.reviewed_by_user_id))
        for req in requests
    ]


@router.post("/registration-requests/{request_id}/approve", response_model=RegisterRequestOut)
def approve_registration_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_approve_registration)),
    sensitive_action: SensitiveActionContext = Depends(
        require_sensitive_action("user.approve_registration")
    ),
) -> RegisterRequestOut:
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
    try:
        validate_registration_status_change(
            current_status=req.status,
            target_status=RegistrationRequestStatus.approved,
        )
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    exists = db.query(User).filter(User.username == req.username).first()
    if exists:
        try:
            validate_registration_status_change(
                current_status=req.status,
                target_status=RegistrationRequestStatus.rejected,
            )
        except BusinessRuleViolation as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        before_status = req.status
        req.status = RegistrationRequestStatus.rejected
        req.reviewed_by_user_id = admin.id
        req.reviewed_at = _utcnow()
        req.rejection_reason = "username_exists"
        record_audit_log(
            db,
            actor=admin,
            action="registration.request.review",
            entity_type="registration_request",
            entity_id=str(req.id),
            description="Registration request auto-rejected due to username conflict",
            before={"status": before_status.value},
            after={"status": req.status.value},
            metadata={
                "audit_category": "approval",
                "critical": True,
                "decision": "auto_reject_conflict",
                "username": req.username,
                "sensitive_action": sensitive_action.action,
                "confirmation_required": sensitive_action.confirmation_required,
                "confirmation_provided": sensitive_action.confirmation_provided,
                "step_up_required": sensitive_action.step_up_required,
                "step_up_satisfied": sensitive_action.step_up_satisfied,
                "request_id": sensitive_action.request_id,
            },
        )
        emit_domain_event(
            db,
            actor=admin,
            event_name="registration.request.rejected",
            entity_type="registration_request",
            entity_id=str(req.id),
            payload={
                "from": before_status.value,
                "to": req.status.value,
                "reason": "username_exists",
                "username": req.username,
            },
            description="Registration request auto-rejected because username already exists",
        )
        db.commit()
        db.refresh(req)
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=req.username,
        hashed_password=req.hashed_password,
        role=UserRole.editor,
        is_active=True,
        needs_password_setup=False,
    )
    db.add(user)
    before_status = req.status
    req.status = RegistrationRequestStatus.approved
    req.reviewed_by_user_id = admin.id
    req.reviewed_at = _utcnow()
    req.rejection_reason = None
    record_audit_log(
        db,
        actor=admin,
        action="registration.request.review",
        entity_type="registration_request",
        entity_id=str(req.id),
        description="Registration request approved",
        before={"status": before_status.value},
        after={"status": req.status.value},
        metadata={
            "audit_category": "approval",
            "critical": True,
            "decision": "approved",
            "username": req.username,
            "provisioned_role": UserRole.editor.value,
            "sensitive_action": sensitive_action.action,
            "confirmation_required": sensitive_action.confirmation_required,
            "confirmation_provided": sensitive_action.confirmation_provided,
            "step_up_required": sensitive_action.step_up_required,
            "step_up_satisfied": sensitive_action.step_up_satisfied,
            "request_id": sensitive_action.request_id,
        },
    )
    emit_domain_event(
        db,
        actor=admin,
        event_name="registration.request.approved",
        entity_type="registration_request",
        entity_id=str(req.id),
        payload={
            "from": before_status.value,
            "to": req.status.value,
            "username": req.username,
            "provisioned_role": UserRole.editor.value,
        },
        description="Registration request approved and user provisioned",
    )
    db.commit()
    db.refresh(req)
    return _serialize_registration_request(req, admin.username)


@router.post("/registration-requests/{request_id}/reject", response_model=RegisterRequestOut)
def reject_registration_request(
    request_id: uuid.UUID,
    reason: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission(Permission.user_approve_registration)),
    sensitive_action: SensitiveActionContext = Depends(
        require_sensitive_action("user.reject_registration")
    ),
) -> RegisterRequestOut:
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if not reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    try:
        validate_registration_status_change(
            current_status=req.status,
            target_status=RegistrationRequestStatus.rejected,
        )
    except BusinessRuleViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    before_status = req.status
    req.status = RegistrationRequestStatus.rejected
    req.reviewed_by_user_id = admin.id
    req.reviewed_at = _utcnow()
    req.rejection_reason = reason.strip()
    record_audit_log(
        db,
        actor=admin,
        action="registration.request.review",
        entity_type="registration_request",
        entity_id=str(req.id),
        description="Registration request rejected",
        before={"status": before_status.value},
        after={"status": req.status.value, "rejection_reason": req.rejection_reason},
        metadata={
            "audit_category": "approval",
            "critical": True,
            "decision": "rejected",
            "username": req.username,
            "rejection_reason": req.rejection_reason,
            "sensitive_action": sensitive_action.action,
            "confirmation_required": sensitive_action.confirmation_required,
            "confirmation_provided": sensitive_action.confirmation_provided,
            "step_up_required": sensitive_action.step_up_required,
            "step_up_satisfied": sensitive_action.step_up_satisfied,
            "request_id": sensitive_action.request_id,
        },
    )
    emit_domain_event(
        db,
        actor=admin,
        event_name="registration.request.rejected",
        entity_type="registration_request",
        entity_id=str(req.id),
        payload={
            "from": before_status.value,
            "to": req.status.value,
            "username": req.username,
        },
        description="Registration request rejected",
    )
    db.commit()
    db.refresh(req)
    return _serialize_registration_request(req, admin.username)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    context: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)
) -> list[SessionOut]:
    now = _utcnow()
    sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == context.user.id, AuthSession.expires_at > now)
        .order_by(AuthSession.last_activity_at.desc())
        .all()
    )
    return [
        SessionOut(
            id=session.id,
            created_at=session.created_at,
            last_activity_at=session.last_activity_at,
            expires_at=session.expires_at,
            idle_expires_at=session.idle_expires_at,
            ip_address=session.ip_address,
            device_label=session.device_label,
            user_agent=session.user_agent,
            mfa_verified=session.mfa_verified,
            is_current=session.id == context.session.id,
        )
        for session in sessions
        if session.revoked_at is None
    ]


@router.delete("/sessions/{session_id}")
def revoke_single_session(
    session_id: uuid.UUID,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    session = (
        db.query(AuthSession)
        .filter(AuthSession.id == session_id, AuthSession.user_id == context.user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    record_audit_log(
        db,
        actor=context.user,
        action="auth.session.revoke",
        entity_type="auth_session",
        entity_id=str(session.id),
        description="Session revoked by user",
        before={
            "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
            "mfa_verified": bool(session.mfa_verified),
        },
        after={"revoked_at": _utcnow().isoformat(), "reason": "manual_revoke"},
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    revoke_session(db, session=session, reason="manual_revoke")
    db.commit()
    if session.id == context.session.id:
        _clear_auth_cookies(response)
    return {"ok": "true"}


@router.get("/login-history", response_model=list[LoginHistoryOut])
def get_login_history(
    limit: int = Query(default=50, ge=1, le=200),
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> list[LoginHistoryOut]:
    rows = (
        db.query(LoginHistory)
        .filter(LoginHistory.user_id == context.user.id)
        .order_by(LoginHistory.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [
        LoginHistoryOut(
            id=row.id,
            username=row.username,
            occurred_at=row.occurred_at,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            success=row.success,
            suspicious=row.suspicious,
            reason=row.reason,
        )
        for row in rows
    ]


@router.get("/mfa/status", response_model=MfaStatusOut)
def mfa_status(current_user: User = Depends(get_current_user)) -> MfaStatusOut:
    return MfaStatusOut(enabled=bool(current_user.mfa_enabled))


@router.post("/mfa/provision", response_model=MfaProvisionOut)
def mfa_provision(context: AuthContext = Depends(get_current_auth_context)) -> MfaProvisionOut:
    secret = create_totp_secret()
    return MfaProvisionOut(
        secret=secret, otpauth_uri=totp_uri(username=context.user.username, secret=secret)
    )


@router.post("/mfa/enable", response_model=MfaEnableOut)
def mfa_enable(
    request: Request,
    response: Response,
    payload: MfaEnableIn,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> MfaEnableOut:
    if not verify_totp_code(payload.secret, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")

    codes = generate_recovery_codes()
    context.user.mfa_secret = payload.secret
    context.user.mfa_enabled = True
    context.user.mfa_recovery_codes = hash_recovery_codes(codes)
    context.session.mfa_verified = True
    record_audit_log(
        db,
        actor=context.user,
        action="auth.mfa.enable",
        entity_type="user",
        entity_id=str(context.user.id),
        description="Enabled MFA for account",
        before={"mfa_enabled": False},
        after={"mfa_enabled": True, "recovery_codes_count": len(codes)},
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    access_token, refresh_token_value, _, _ = rotate_refresh_token(
        db, user=context.user, session=context.session
    )
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, context.session)
    return MfaEnableOut(recovery_codes=codes)


@router.post("/mfa/disable", response_model=MfaStatusOut)
def mfa_disable(
    request: Request,
    response: Response,
    payload: MfaDisableIn,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> MfaStatusOut:
    if not verify_password(payload.password, context.user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid password")
    if not _verify_mfa(context.user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")

    context.user.mfa_secret = None
    context.user.mfa_enabled = False
    context.user.mfa_recovery_codes = None
    context.session.mfa_verified = False
    record_audit_log(
        db,
        actor=context.user,
        action="auth.mfa.disable",
        entity_type="user",
        entity_id=str(context.user.id),
        description="Disabled MFA for account",
        before={"mfa_enabled": True},
        after={"mfa_enabled": False},
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    access_token, refresh_token_value, _, _ = rotate_refresh_token(
        db, user=context.user, session=context.session
    )
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, context.session)
    return MfaStatusOut(enabled=False)


@router.post("/change-password", response_model=TokenOut)
def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordIn,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not verify_password(payload.current_password, context.user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_password = _validate_password_strength(payload.new_password)
    if verify_password(new_password, context.user.hashed_password):
        raise HTTPException(
            status_code=400, detail="New password must differ from current password"
        )

    context.user.hashed_password = hash_password(new_password)
    context.user.password_changed_at = _utcnow()
    context.user.failed_login_attempts = 0
    context.user.locked_until = None

    sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == context.user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for session in sessions:
        if session.id != context.session.id:
            revoke_session(db, session=session, reason="password_changed")

    record_audit_log(
        db,
        actor=context.user,
        action="auth.password.change",
        entity_type="user",
        entity_id=str(context.user.id),
        description="Changed password and revoked other active sessions",
        after={"revoked_other_sessions": len([s for s in sessions if s.id != context.session.id])},
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    access_token, refresh_token_value, _, _ = rotate_refresh_token(
        db, user=context.user, session=context.session
    )
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, context.session)
    return TokenOut(access_token=access_token)


@router.post("/password-reset/request", response_model=PasswordResetRequestOut)
def request_password_reset(
    payload: PasswordResetRequestIn,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetRequestOut:
    username = payload.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return PasswordResetRequestOut(ok=True, reset_token=None)

    now = _utcnow()
    previous_tokens = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .all()
    )
    for token in previous_tokens:
        token.used_at = now

    reset_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(reset_token),
            expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
            requested_ip=get_client_ip(request),
            requested_user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        )
    )
    record_audit_log(
        db,
        actor=user,
        action="auth.password.reset.request",
        entity_type="user",
        entity_id=str(user.id),
        description="Password reset requested",
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
            "active_tokens_invalidated": len(previous_tokens),
        },
    )
    db.commit()
    return PasswordResetRequestOut(ok=True, reset_token=reset_token)


@router.post("/password-reset/confirm", response_model=dict)
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirmIn,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    new_password = _validate_password_strength(payload.new_password)
    token_hash_value = hash_token(payload.token)
    now = _utcnow()
    token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash_value,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .first()
    )
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(new_password)
    user.password_changed_at = now
    user.failed_login_attempts = 0
    user.locked_until = None
    token.used_at = now

    sessions = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for session in sessions:
        revoke_session(db, session=session, reason="password_reset")

    record_audit_log(
        db,
        actor=user,
        action="auth.password.reset.confirm",
        entity_type="user",
        entity_id=str(user.id),
        description="Password reset confirmed and active sessions revoked",
        after={"revoked_sessions": len(sessions)},
        metadata={
            "audit_category": "security",
            "critical": True,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    db.commit()
    return {"ok": "true"}
