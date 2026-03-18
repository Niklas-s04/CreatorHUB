from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.auth_session import RevokedToken
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
