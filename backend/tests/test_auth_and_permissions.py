from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.audit import AuditLog
from app.models.auth_session import AuthSession, RevokedToken
from app.models.product import Product
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import UserRole
from tests.factories import DEFAULT_PASSWORD, create_tokens_for_user, create_user


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_success_sets_auth_and_csrf_cookies(client, db_session: Session) -> None:
    create_user(db_session, username="admin_user", role=UserRole.admin)

    response = client.post(
        "/api/auth/token",
        data={"username": "admin_user", "password": DEFAULT_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    assert client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    assert client.cookies.get(settings.CSRF_COOKIE_NAME)


def test_failed_logins_trigger_account_lock(client, db_session: Session) -> None:
    user = create_user(db_session, username="editor_lock", role=UserRole.editor)

    for _ in range(settings.AUTH_MAX_FAILED_ATTEMPTS):
        response = client.post(
            "/api/auth/token",
            data={"username": user.username, "password": "wrong-password"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401

    locked_response = client.post(
        "/api/auth/token",
        data={"username": user.username, "password": "wrong-password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert locked_response.status_code == 429


def test_permission_route_denies_viewer_and_allows_admin(client, app, db_session: Session) -> None:
    admin = create_user(db_session, username="admin_list", role=UserRole.admin)
    viewer = create_user(db_session, username="viewer_list", role=UserRole.viewer)

    viewer_token, _ = create_tokens_for_user(db_session, user=viewer)
    denied = client.get("/api/auth/users", headers=_auth_header(viewer_token))
    assert denied.status_code == 403

    admin_token, _ = create_tokens_for_user(db_session, user=admin)
    allowed = client.get("/api/auth/users", headers=_auth_header(admin_token))
    assert allowed.status_code == 200
    assert any(entry["username"] == admin.username for entry in allowed.json())


def test_me_rejects_refresh_token_type(client, db_session: Session) -> None:
    user = create_user(db_session, username="wrong_type", role=UserRole.editor)
    _, refresh_token = create_tokens_for_user(db_session, user=user)

    response = client.get("/api/auth/me", headers=_auth_header(refresh_token))
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_me_rejects_revoked_token(client, db_session: Session) -> None:
    user = create_user(db_session, username="revoked", role=UserRole.editor)
    access_token, _ = create_tokens_for_user(db_session, user=user)

    payload_jti = deps.decode_token(access_token).get("jti")
    db_session.add(
        RevokedToken(
            jti=payload_jti,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
    )
    db_session.commit()

    response = client.get("/api/auth/me", headers=_auth_header(access_token))
    assert response.status_code == 401
    assert response.json()["detail"] == "Token revoked"


def test_create_user_requires_admin_role(client, db_session: Session) -> None:
    viewer = create_user(db_session, username="viewer_create_user", role=UserRole.viewer)
    access_token, _ = create_tokens_for_user(db_session, user=viewer)

    response = client.post(
        "/api/auth/users",
        json={"username": "new_editor", "password": "NewStrong!Pass123", "role": "editor"},
        headers=_auth_header(access_token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_create_user_writes_audit_log(client, db_session: Session) -> None:
    admin = create_user(db_session, username="admin_create_audit", role=UserRole.admin)
    access_token, _ = create_tokens_for_user(db_session, user=admin)

    response = client.post(
        "/api/auth/users",
        json={"username": "new_editor_audit", "password": "NewStrong!Pass123", "role": "editor"},
        headers=_auth_header(access_token),
    )

    assert response.status_code == 200
    created_user = response.json()

    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "user.create", AuditLog.entity_id == created_user["id"])
        .first()
    )
    assert audit is not None
    assert isinstance(audit.meta, dict)
    assert audit.meta.get("audit_category") == "permission_change"
    assert bool(audit.meta.get("critical")) is True


def test_me_includes_effective_permissions(client, db_session: Session) -> None:
    editor = create_user(db_session, username="perm_editor", role=UserRole.editor)
    access_token, _ = create_tokens_for_user(db_session, user=editor)

    response = client.get("/api/auth/me", headers=_auth_header(access_token))

    assert response.status_code == 200
    body = response.json()
    assert "permissions" in body
    assert "email.generate" in body["permissions"]
    assert "product.delete" not in body["permissions"]


def test_product_delete_requires_dedicated_permission(client, db_session: Session) -> None:
    product = Product(title="Delete Me")
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    editor = create_user(db_session, username="editor_delete_perm", role=UserRole.editor)
    editor_token, _ = create_tokens_for_user(db_session, user=editor)

    denied = client.delete(f"/api/products/{product.id}", headers=_auth_header(editor_token))
    assert denied.status_code == 403


def test_approve_registration_requires_sensitive_confirmation_when_enabled(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "SECURITY_SENSITIVE_ACTION_CONFIRMATION_REQUIRED", True)
    monkeypatch.setattr(settings, "SECURITY_SENSITIVE_ACTION_CONFIRMATION_VALUE", "CONFIRM")

    admin = create_user(db_session, username="admin_confirm", role=UserRole.admin)
    token, _ = create_tokens_for_user(db_session, user=admin)

    req = RegistrationRequest(
        username="pending_confirm_user",
        hashed_password="hashed",
        status=RegistrationRequestStatus.pending,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    denied = client.post(
        f"/api/auth/registration-requests/{req.id}/approve",
        headers=_auth_header(token),
    )
    assert denied.status_code == 428

    allowed = client.post(
        f"/api/auth/registration-requests/{req.id}/approve",
        headers={**_auth_header(token), "x-action-confirm": "CONFIRM"},
    )
    assert allowed.status_code == 200


def test_approve_registration_requires_step_up_mfa_when_enabled(
    client,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA", True)

    admin = create_user(db_session, username="admin_stepup", role=UserRole.admin)
    token, _ = create_tokens_for_user(db_session, user=admin)

    req = RegistrationRequest(
        username="pending_stepup_user",
        hashed_password="hashed",
        status=RegistrationRequestStatus.pending,
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    denied = client.post(
        f"/api/auth/registration-requests/{req.id}/approve",
        headers=_auth_header(token),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Step-up authentication required"

    session = db_session.query(AuthSession).filter(AuthSession.user_id == admin.id).first()
    assert session is not None
    session.mfa_verified = True
    db_session.commit()

    allowed = client.post(
        f"/api/auth/registration-requests/{req.id}/approve",
        headers=_auth_header(token),
    )
    assert allowed.status_code == 200


def test_update_user_blocks_self_role_or_status_change(client, db_session: Session) -> None:
    admin = create_user(db_session, username="admin_self_guard", role=UserRole.admin)
    token, _ = create_tokens_for_user(db_session, user=admin)

    response = client.patch(
        f"/api/auth/users/{admin.id}?role=editor",
        headers=_auth_header(token),
    )

    assert response.status_code == 400
    assert "Self role/status changes" in response.json()["detail"]


def test_update_user_writes_revision_safe_audit_log(client, db_session: Session) -> None:
    admin = create_user(db_session, username="admin_audit_guard", role=UserRole.admin)
    target = create_user(db_session, username="target_editor", role=UserRole.editor)
    token, _ = create_tokens_for_user(db_session, user=admin)

    response = client.patch(
        f"/api/auth/users/{target.id}?role=viewer",
        headers=_auth_header(token),
    )
    assert response.status_code == 200

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "user.role_or_status.update",
            AuditLog.entity_id == str(target.id),
        )
        .first()
    )
    assert audit is not None
    assert audit.before is not None
    assert audit.after is not None
    assert audit.before.get("role") == "editor"
    assert audit.after.get("role") == "viewer"


def test_confirm_password_reset_writes_security_audit(client, db_session: Session) -> None:
    user = create_user(db_session, username="reset_audit_user", role=UserRole.editor)

    request_response = client.post(
        "/api/auth/password-reset/request",
        json={"username": user.username},
    )
    assert request_response.status_code == 200
    reset_token = request_response.json().get("reset_token")
    assert isinstance(reset_token, str) and reset_token

    confirm_response = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "ResetStrong!Pass123"},
    )
    assert confirm_response.status_code == 200

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "auth.password.reset.confirm",
            AuditLog.entity_id == str(user.id),
        )
        .first()
    )
    assert audit is not None
    assert isinstance(audit.meta, dict)
    assert audit.meta.get("audit_category") == "security"
    assert bool(audit.meta.get("critical")) is True
