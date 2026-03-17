from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import hashlib
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
