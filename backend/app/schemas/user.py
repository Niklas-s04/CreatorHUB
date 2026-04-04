from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
    needs_password_setup: bool
    mfa_enabled: bool
    locked_until: datetime | None = None
    last_activity_at: datetime | None = None
    active_sessions: int = 0
    permissions: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.editor
