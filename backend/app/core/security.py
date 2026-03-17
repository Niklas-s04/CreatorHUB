from __future__ import annotations

import base64
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import hashlib
import secrets
import uuid

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def new_jti() -> str:
    return uuid.uuid4().hex


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _csrf_signature(session_id: str, nonce: str) -> str:
    digest = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        f"csrf:{session_id}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def create_csrf_token(session_id: str) -> str:
    nonce = secrets.token_urlsafe(24)
    signature = _csrf_signature(session_id, nonce)
    return f"{nonce}.{signature}"


def validate_csrf_token(token: str, session_id: str) -> bool:
    if not token or "." not in token:
        return False
    nonce, signature = token.split(".", 1)
    expected = _csrf_signature(session_id, nonce)
    return hmac.compare_digest(signature, expected)


def create_access_token(
    *,
    subject: str,
    role: str,
    session_id: str,
    jti: str,
    expires_minutes: Optional[int] = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.JWT_ACCESS_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "role": role, "sid": session_id, "jti": jti, "typ": "access", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(
    *,
    subject: str,
    role: str,
    session_id: str,
    jti: str,
    expires_minutes: Optional[int] = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.JWT_REFRESH_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "role": role, "sid": session_id, "jti": jti, "typ": "refresh", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
