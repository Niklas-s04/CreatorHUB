from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_db, get_current_auth_context, get_current_user, require_role, get_client_ip
from app.core.security import verify_password, hash_password, decode_token, hash_token, create_csrf_token
from app.core.config import settings
from app.models.auth_session import AuthSession, LoginHistory, PasswordResetToken
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.auth import (
    TokenOut,
    AdminBootstrapStatusOut,
    AdminPasswordSetupIn,
    RegisterRequestIn,
    RegisterRequestOut,
    SessionOut,
    LoginHistoryOut,
    MfaStatusOut,
    MfaProvisionOut,
    MfaEnableIn,
    MfaDisableIn,
    MfaEnableOut,
    ChangePasswordIn,
    PasswordResetRequestIn,
    PasswordResetRequestOut,
    PasswordResetConfirmIn,
)
from app.schemas.user import UserOut, UserCreate
from app.services.audit import record_audit_log
from app.services.bootstrap import assert_bootstrap_active, assert_valid_bootstrap_token, finalize_bootstrap
from app.services.auth_security import (
    create_session_and_tokens,
    rotate_refresh_token,
    revoke_session,
    revoke_token,
    is_token_revoked,
    record_login_attempt,
    is_suspicious_login,
    create_totp_secret,
    totp_uri,
    verify_totp_code,
    generate_recovery_codes,
    hash_recovery_codes,
    verify_recovery_code,
)

router = APIRouter()
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")


def _validate_username(username: str) -> str:
    candidate = username.strip()
    if not USERNAME_RE.match(candidate):
        raise HTTPException(status_code=400, detail="Username must be 3-64 chars and only contain letters, numbers, . _ -")
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
        raise HTTPException(status_code=400, detail="Password must include upper/lowercase letters, a number, and a special character")
    return candidate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    access_max_age = max(1, min(settings.AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS, absolute_remaining, idle_remaining))
    refresh_max_age = max(1, min(settings.AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS, absolute_remaining))
    csrf_max_age = access_max_age
    return access_max_age, refresh_max_age, csrf_max_age


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str, session: AuthSession) -> None:
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin password setup required")

    if user and not user.is_active:
        suspicious = is_suspicious_login(db, user=user, ip_address=ip_address, user_agent=user_agent, success=False)
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    if user and user.locked_until and user.locked_until > _utcnow():
        suspicious = is_suspicious_login(db, user=user, ip_address=ip_address, user_agent=user_agent, success=False)
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
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account temporarily locked")

    if not user or not verify_password(form_data.password, user.hashed_password):
        suspicious = is_suspicious_login(db, user=user, ip_address=ip_address, user_agent=user_agent, success=False)
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    if user.mfa_enabled:
        if not otp or not _verify_mfa(user, otp):
            _apply_failed_login(user)
            suspicious = is_suspicious_login(db, user=user, ip_address=ip_address, user_agent=user_agent, success=False)
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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA required or invalid")

    user.failed_login_attempts = 0
    user.locked_until = None
    suspicious = is_suspicious_login(db, user=user, ip_address=ip_address, user_agent=user_agent, success=True)
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
        return AdminBootstrapStatusOut(admin_username=settings.BOOTSTRAP_ADMIN_USERNAME, needs_password_setup=True)
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
            "bootstrap_completed_at": bootstrap_state.setup_completed_at.isoformat() if bootstrap_state.setup_completed_at else None,
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if is_token_revoked(db, jti=jti):
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    try:
        session_id = uuid.UUID(str(sid))
    except Exception:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.user_id == user.id).first()
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid")

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
    for token_value in [t for t in token_values if t]:
        try:
            payload = decode_token(token_value)
            jti = payload.get("jti")
            sid = payload.get("sid")
            if jti:
                revoke_token(db, jti=jti, expires_at=_safe_exp_from_payload(payload))
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
    return {"ok": "true"}


@router.post("/register-request", response_model=RegisterRequestOut)
def register_request(payload: RegisterRequestIn, db: Session = Depends(get_db)) -> RegisterRequestOut:
    username = _validate_username(payload.username)
    password = _validate_password_strength(payload.password)

    if username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Username is reserved")

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    existing_request = db.query(RegistrationRequest).filter(RegistrationRequest.username == username).first()
    if existing_request:
        if existing_request.status == RegistrationRequestStatus.pending:
            raise HTTPException(status_code=400, detail="Registration request already pending")
        existing_request.hashed_password = hash_password(password)
        existing_request.status = RegistrationRequestStatus.pending
        existing_request.reviewed_by_user_id = None
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
        .filter(AuthSession.user_id == current_user.id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > _utcnow())
        .count()
    )
    current_user.active_sessions = active_sessions
    return current_user


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_role(UserRole.admin))) -> UserOut:
    username = _validate_username(payload.username)
    password = _validate_password_strength(payload.password)

    if username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower() or payload.role == UserRole.admin:
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
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role(UserRole.admin))) -> list[UserOut]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    user_ids = [u.id for u in users]
    counts: dict[uuid.UUID, int] = {}
    if user_ids:
        rows = (
            db.query(AuthSession.user_id)
            .filter(AuthSession.user_id.in_(user_ids), AuthSession.revoked_at.is_(None), AuthSession.expires_at > _utcnow())
            .all()
        )
        for row in rows:
            counts[row[0]] = counts.get(row[0], 0) + 1

    return [
        UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            needs_password_setup=user.needs_password_setup,
            mfa_enabled=user.mfa_enabled,
            active_sessions=counts.get(user.id, 0),
        )
        for user in users
    ]


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    role: UserRole | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
) -> UserOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username.lower() == settings.BOOTSTRAP_ADMIN_USERNAME.lower():
        raise HTTPException(status_code=400, detail="Admin account is managed separately")
    if role is not None:
        if role == UserRole.admin:
            raise HTTPException(status_code=400, detail="Only the bootstrap admin account can be admin")
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/registration-requests", response_model=list[RegisterRequestOut])
def list_registration_requests(
    status_filter: RegistrationRequestStatus | None = RegistrationRequestStatus.pending,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
) -> list[RegisterRequestOut]:
    query = db.query(RegistrationRequest)
    if status_filter is not None:
        query = query.filter(RegistrationRequest.status == status_filter)
    return query.order_by(RegistrationRequest.created_at.desc()).all()


@router.post("/registration-requests/{request_id}/approve", response_model=RegisterRequestOut)
def approve_registration_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.admin)),
) -> RegisterRequestOut:
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if req.status != RegistrationRequestStatus.pending:
        raise HTTPException(status_code=409, detail="Registration request already processed")

    exists = db.query(User).filter(User.username == req.username).first()
    if exists:
        req.status = RegistrationRequestStatus.rejected
        req.reviewed_by_user_id = admin.id
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
    req.status = RegistrationRequestStatus.approved
    req.reviewed_by_user_id = admin.id
    db.commit()
    db.refresh(req)
    return req


@router.post("/registration-requests/{request_id}/reject", response_model=RegisterRequestOut)
def reject_registration_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.admin)),
) -> RegisterRequestOut:
    req = db.query(RegistrationRequest).filter(RegistrationRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if req.status != RegistrationRequestStatus.pending:
        raise HTTPException(status_code=409, detail="Registration request already processed")

    req.status = RegistrationRequestStatus.rejected
    req.reviewed_by_user_id = admin.id
    db.commit()
    db.refresh(req)
    return req


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(context: AuthContext = Depends(get_current_auth_context), db: Session = Depends(get_db)) -> list[SessionOut]:
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
    response: Response,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.user_id == context.user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
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
    return MfaProvisionOut(secret=secret, otpauth_uri=totp_uri(username=context.user.username, secret=secret))


@router.post("/mfa/enable", response_model=MfaEnableOut)
def mfa_enable(
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
    access_token, refresh_token_value, _, _ = rotate_refresh_token(db, user=context.user, session=context.session)
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, context.session)
    return MfaEnableOut(recovery_codes=codes)


@router.post("/mfa/disable", response_model=MfaStatusOut)
def mfa_disable(
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
    access_token, refresh_token_value, _, _ = rotate_refresh_token(db, user=context.user, session=context.session)
    db.commit()
    _set_auth_cookies(response, access_token, refresh_token_value, context.session)
    return MfaStatusOut(enabled=False)


@router.post("/change-password", response_model=TokenOut)
def change_password(
    response: Response,
    payload: ChangePasswordIn,
    context: AuthContext = Depends(get_current_auth_context),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not verify_password(payload.current_password, context.user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_password = _validate_password_strength(payload.new_password)
    if verify_password(new_password, context.user.hashed_password):
        raise HTTPException(status_code=400, detail="New password must differ from current password")

    context.user.hashed_password = hash_password(new_password)
    context.user.password_changed_at = _utcnow()
    context.user.failed_login_attempts = 0
    context.user.locked_until = None

    sessions = db.query(AuthSession).filter(AuthSession.user_id == context.user.id, AuthSession.revoked_at.is_(None)).all()
    for session in sessions:
        if session.id != context.session.id:
            revoke_session(db, session=session, reason="password_changed")

    access_token, refresh_token_value, _, _ = rotate_refresh_token(db, user=context.user, session=context.session)
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
    db.commit()
    return PasswordResetRequestOut(ok=True, reset_token=reset_token)


@router.post("/password-reset/confirm", response_model=dict)
def confirm_password_reset(payload: PasswordResetConfirmIn, db: Session = Depends(get_db)) -> dict[str, str]:
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

    sessions = db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).all()
    for session in sessions:
        revoke_session(db, session=session, reason="password_reset")

    db.commit()
    return {"ok": "true"}
