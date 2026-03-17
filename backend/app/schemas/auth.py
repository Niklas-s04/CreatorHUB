from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.registration_request import RegistrationRequestStatus


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
