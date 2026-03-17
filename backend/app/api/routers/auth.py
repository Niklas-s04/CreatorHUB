from __future__ import annotations

import re
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.security import verify_password, create_access_token, hash_password
from app.core.config import settings
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.auth import (
    TokenOut,
    AdminBootstrapStatusOut,
    AdminPasswordSetupIn,
    RegisterRequestIn,
    RegisterRequestOut,
)
from app.schemas.user import UserOut, UserCreate

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


def _set_auth_cookies(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.AUTH_COOKIE_MAX_AGE_SECONDS,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(24),
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.AUTH_COOKIE_MAX_AGE_SECONDS,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


@router.post("/token", response_model=TokenOut)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenOut:
    username = form_data.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if user and user.role == UserRole.admin and user.needs_password_setup:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin password setup required")
    if user and not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token(subject=user.username, role=user.role.value)
    _set_auth_cookies(response, token)
    return TokenOut(access_token=token)


@router.get("/bootstrap-status", response_model=AdminBootstrapStatusOut)
def bootstrap_status(db: Session = Depends(get_db)) -> AdminBootstrapStatusOut:
    admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
    if not admin:
        return AdminBootstrapStatusOut(admin_username=settings.BOOTSTRAP_ADMIN_USERNAME, needs_password_setup=True)
    return AdminBootstrapStatusOut(
        admin_username=admin.username,
        needs_password_setup=bool(admin.needs_password_setup),
    )


@router.post("/setup-admin-password", response_model=TokenOut)
def setup_admin_password(response: Response, payload: AdminPasswordSetupIn, db: Session = Depends(get_db)) -> TokenOut:
    password = _validate_password_strength(payload.password)

    admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found")
    if not admin.needs_password_setup:
        raise HTTPException(status_code=409, detail="Admin password already set")

    admin.hashed_password = hash_password(password)
    admin.needs_password_setup = False
    admin.is_active = True
    db.commit()
    token = create_access_token(subject=admin.username, role=admin.role.value)
    _set_auth_cookies(response, token)
    return TokenOut(access_token=token)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
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
def me(current_user: User = Depends(get_current_user)) -> UserOut:
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
    user = User(username=username, hashed_password=hash_password(password), role=payload.role, needs_password_setup=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role(UserRole.admin))) -> list[UserOut]:
    return db.query(User).order_by(User.created_at.desc()).all()


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
