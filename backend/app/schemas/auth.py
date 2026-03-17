from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.registration_request import RegistrationRequestStatus


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    idle_expires_at: datetime
    ip_address: str | None
    device_label: str | None
    user_agent: str | None
    mfa_verified: bool
    is_current: bool = False


class LoginHistoryOut(BaseModel):
    id: uuid.UUID
    username: str | None
    occurred_at: datetime
    ip_address: str | None
    user_agent: str | None
    success: bool
    suspicious: bool
    reason: str | None


class MfaStatusOut(BaseModel):
    enabled: bool


class MfaProvisionOut(BaseModel):
    secret: str
    otpauth_uri: str


class MfaEnableIn(BaseModel):
    secret: str
    code: str


class MfaDisableIn(BaseModel):
    password: str
    code: str


class MfaEnableOut(BaseModel):
    recovery_codes: list[str]


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequestIn(BaseModel):
    username: str


class PasswordResetRequestOut(BaseModel):
    ok: bool = True
    reset_token: str | None = None


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str


class AdminBootstrapStatusOut(BaseModel):
    admin_username: str
    needs_password_setup: bool


class AdminPasswordSetupIn(BaseModel):
    password: str


class RegisterRequestIn(BaseModel):
    username: str
    password: str


class RegisterRequestOut(BaseModel):
    id: uuid.UUID
    username: str
    status: RegistrationRequestStatus

    class Config:
        from_attributes = True
