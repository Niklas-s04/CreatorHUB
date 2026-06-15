import base64
import hashlib
import ipaddress
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from passlib.hash import pbkdf2_sha256
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


_redis_client: Redis | None = None


def _get_redis() -> Redis | None:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        _redis_client = Redis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
        )
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None


def _redis_revoke_key(jti: str) -> str:
    return f"auth:deny:jti:{jti}"


def _normalize_reset_ip(ip_address: str | None) -> str | None:
    candidate = (ip_address or "").strip()
    if not candidate:
        return None

    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return candidate.lower()

    if address.version == 4:
        network = ipaddress.ip_network(f"{address}/24", strict=False)
    else:
        network = ipaddress.ip_network(f"{address}/64", strict=False)
    return network.with_prefixlen


def _normalize_reset_user_agent(user_agent: str | None) -> str | None:
    candidate = (user_agent or "").strip()
    if not candidate:
        return None
    return candidate.lower()


def hash_password_reset_context(
    ip_address: str | None, user_agent: str | None
) -> tuple[str | None, str | None]:
    normalized_ip = _normalize_reset_ip(ip_address)
    normalized_user_agent = _normalize_reset_user_agent(user_agent)
    return (
        hash_token(f"ip:{normalized_ip}") if normalized_ip else None,
        hash_token(f"ua:{normalized_user_agent}") if normalized_user_agent else None,
    )


def password_reset_context_matches(
    stored_ip_hash: str | None,
    stored_user_agent_hash: str | None,
    current_ip: str | None,
    current_user_agent: str | None,
) -> bool:
    current_ip_hash, current_user_agent_hash = hash_password_reset_context(
        current_ip, current_user_agent
    )

    if stored_ip_hash and current_ip_hash != stored_ip_hash:
        return False
    if stored_user_agent_hash and current_user_agent_hash != stored_user_agent_hash:
        return False
    return True


def revoke_token(db: Session, *, jti: str, expires_at: datetime) -> None:
    for pending in db.new:
        if isinstance(pending, RevokedToken) and pending.jti == jti:
            break
    else:
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
        mfa_step_up_expires_at=now
        + timedelta(seconds=settings.SECURITY_STEP_UP_MFA_MAX_AGE_SECONDS)
        if mfa_verified
        else None,
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


def rotate_refresh_token(
    db: Session, *, user: User, session: AuthSession
) -> tuple[str, str, str, str]:
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
        revoke_token(
            db,
            jti=old_refresh_jti,
            expires_at=now + timedelta(minutes=settings.JWT_REFRESH_EXPIRE_MINUTES),
        )
    if old_access_jti:
        revoke_token(
            db,
            jti=old_access_jti,
            expires_at=now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
        )

    return access_token, refresh_token, access_jti, refresh_jti


def revoke_session(db: Session, *, session: AuthSession, reason: str) -> None:
    if session.revoked_at is None:
        now = utcnow()
        session.revoked_at = now
        session.revoked_reason = reason
        if session.refresh_jti:
            revoke_token(db, jti=session.refresh_jti, expires_at=session.expires_at)
        if session.last_access_jti:
            revoke_token(
                db,
                jti=session.last_access_jti,
                expires_at=now + timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
            )


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


def is_suspicious_login(
    db: Session, *, user: User | None, ip_address: str | None, user_agent: str | None, success: bool
) -> bool:
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


def _mfa_fernet() -> Fernet:
    digest = hashlib.sha256(f"{settings.JWT_SECRET}:mfa-totp".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def protect_totp_secret(secret: str) -> str:
    raw = (secret or "").strip()
    if not raw:
        return raw
    if raw.startswith("enc:v1:"):
        return raw
    return "enc:v1:" + _mfa_fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def unprotect_totp_secret(secret: str) -> str:
    raw = (secret or "").strip()
    if not raw or not raw.startswith("enc:v1:"):
        return raw
    token = raw.removeprefix("enc:v1:")
    try:
        return _mfa_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError):
        return ""


def verify_totp_code(secret: str, code: str) -> bool:
    secret = unprotect_totp_secret(secret)
    token = (code or "").replace(" ", "").strip()
    if not token:
        return False
    return bool(pyotp.TOTP(secret).verify(token, valid_window=1))


def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(8).upper() for _ in range(settings.MFA_RECOVERY_CODES_COUNT)]


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [pbkdf2_sha256.hash(code.strip().upper()) for code in codes]


def verify_recovery_code(stored_hashes: list[str] | None, code: str) -> tuple[bool, list[str]]:
    hashes = list(stored_hashes or [])
    candidate = (code or "").strip().upper()
    legacy_candidate = hash_token(candidate)
    for stored_hash in hashes:
        verified = False
        if stored_hash.startswith("$pbkdf2-sha256$"):
            verified = pbkdf2_sha256.verify(candidate, stored_hash)
        else:
            verified = stored_hash == legacy_candidate
        if verified:
            hashes.remove(stored_hash)
            return True, hashes
    return False, hashes
