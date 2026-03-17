from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    new_jti,
)
from app.models.auth_session import AuthSession, LoginHistory, RevokedToken
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_redis() -> Redis | None:
    try:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return client
    except Exception:
        return None


def _redis_revoke_key(jti: str) -> str:
    return f"auth:deny:jti:{jti}"


def revoke_token(db: Session, *, jti: str, expires_at: datetime) -> None:
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if existing is None:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))

    ttl = max(1, int((expires_at - utcnow()).total_seconds()))
    redis_client = _get_redis()
    if redis_client is not None:
        try:
            redis_client.setex(_redis_revoke_key(jti), ttl, "1")
        except RedisError:
            pass


def is_token_revoked(db: Session, *, jti: str) -> bool:
    redis_client = _get_redis()
    if redis_client is not None:
        try:
            if redis_client.exists(_redis_revoke_key(jti)):
                return True
        except RedisError:
            pass

    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None


def build_device_label(user_agent: str | None) -> str:
    if not user_agent:
        return "Unknown"
    ua = user_agent.lower()
    if "windows" in ua:
        platform = "Windows"
    elif "mac" in ua:
        platform = "macOS"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = "Other"

    if "chrome" in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"
    elif "edge" in ua:
        browser = "Edge"
    else:
        browser = "Browser"

    return f"{platform} / {browser}"


def create_session_and_tokens(
    db: Session,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
    mfa_verified: bool,
) -> tuple[AuthSession, str, str, str, str]:
    now = utcnow()
    session_expires = now + timedelta(minutes=settings.SESSION_ABSOLUTE_TIMEOUT_MINUTES)
    idle_expires = now + timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)

    refresh_jti = new_jti()
    access_jti = new_jti()

    session = AuthSession(
        user_id=user.id,
        refresh_jti=refresh_jti,
        refresh_token_hash="pending",
        last_access_jti=access_jti,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        device_label=build_device_label(user_agent),
        mfa_verified=mfa_verified,
        last_activity_at=now,
        idle_expires_at=idle_expires,
        expires_at=session_expires,
    )
    db.add(session)
    db.flush()

    access_token = create_access_token(
        subject=user.username,
        role=user.role.value,
        session_id=str(session.id),
        jti=access_jti,
    )
    refresh_token = create_refresh_token(
        subject=user.username,
        role=user.role.value,
        session_id=str(session.id),
        jti=refresh_jti,
    )
    session.refresh_token_hash = hash_token(refresh_token)
    db.flush()
    return session, access_token, refresh_token, access_jti, refresh_jti


def rotate_refresh_token(db: Session, *, user: User, session: AuthSession) -> tuple[str, str, str, str]:
    old_refresh_jti = session.refresh_jti
    old_access_jti = session.last_access_jti

    access_jti = new_jti()
    refresh_jti = new_jti()
    access_token = create_access_token(
        subject=user.username,
        role=user.role.value,
        session_id=str(session.id),
        jti=access_jti,
    )
    refresh_token = create_refresh_token(
        subject=user.username,
        role=user.role.value,
        session_id=str(session.id),
        jti=refresh_jti,
    )

    now = utcnow()
    session.refresh_jti = refresh_jti
    session.refresh_token_hash = hash_token(refresh_token)
    session.last_access_jti = access_jti
    session.last_activity_at = now
    session.idle_expires_at = now + timedelta(minutes=settings.SESSION_IDLE_TIMEOUT_MINUTES)

    if old_refresh_jti:
        revoke_token(db, jti=old_refresh_jti, expires_at=now + timedelta(minutes=settings.JWT_REFRESH_EXPIRE_MINUTES))
    if old_access_jti:
        revoke_token(db, jti=old_access_jti, expires_at=now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES))

    return access_token, refresh_token, access_jti, refresh_jti


def revoke_session(db: Session, *, session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        now = utcnow()
        session.revoked_at = now
        session.revoked_reason = reason
        if session.refresh_jti:
            revoke_token(db, jti=session.refresh_jti, expires_at=session.expires_at)
        if session.last_access_jti:
            revoke_token(db, jti=session.last_access_jti, expires_at=now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES))


def record_login_attempt(
    db: Session,
    *,
    user: User | None,
    username: str,
    ip_address: str | None,
    user_agent: str | None,
    success: bool,
    suspicious: bool,
    reason: str | None,
) -> None:
    db.add(
        LoginHistory(
            user_id=user.id if user else None,
            username=username,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
            success=success,
            suspicious=suspicious,
            reason=reason,
        )
    )


def is_suspicious_login(db: Session, *, user: User | None, ip_address: str | None, user_agent: str | None, success: bool) -> bool:
    now = utcnow()
    window_start = now - timedelta(minutes=settings.AUTH_SUSPICIOUS_WINDOW_MINUTES)

    if ip_address:
        recent_failed = (
            db.query(LoginHistory)
            .filter(
                LoginHistory.ip_address == ip_address,
                LoginHistory.success.is_(False),
                LoginHistory.occurred_at >= window_start,
            )
            .count()
        )
        if recent_failed >= settings.AUTH_SUSPICIOUS_FAILED_THRESHOLD:
            return True

    if success and user:
        known = (
            db.query(LoginHistory)
            .filter(
                LoginHistory.user_id == user.id,
                LoginHistory.success.is_(True),
                LoginHistory.ip_address == ip_address,
                LoginHistory.user_agent == ((user_agent or "")[:512] or None),
            )
            .count()
        )
        prior_success = (
            db.query(LoginHistory)
            .filter(LoginHistory.user_id == user.id, LoginHistory.success.is_(True))
            .count()
        )
        if prior_success > 0 and known == 0:
            return True

    return False


def create_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(*, username: str, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=settings.MFA_TOTP_ISSUER)


def verify_totp_code(secret: str, code: str) -> bool:
    token = (code or "").replace(" ", "").strip()
    if not token:
        return False
    return bool(pyotp.TOTP(secret).verify(token, valid_window=1))


def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(settings.MFA_RECOVERY_CODES_COUNT)]


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [hash_token(code) for code in codes]


def verify_recovery_code(stored_hashes: list[str] | None, code: str) -> tuple[bool, list[str]]:
    hashes = list(stored_hashes or [])
    candidate = hash_token((code or "").strip().upper())
    if candidate in hashes:
        hashes.remove(candidate)
        return True, hashes
    return False, hashes
