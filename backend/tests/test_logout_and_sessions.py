from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession, RevokedToken
from app.models.user import UserRole
from tests.factories import DEFAULT_PASSWORD, create_tokens_for_user, create_user, login


def test_logout_clears_cookies_and_revokes_session(client, db_session: Session) -> None:
    user = create_user(db_session, username="logout_user", role=UserRole.editor)
    login_state = login(client, username=user.username, password=DEFAULT_PASSWORD)

    response = client.post(
        "/api/auth/logout",
        headers={"x-csrf-token": login_state["csrf"]},
    )

    assert response.status_code == 200
    assert response.json()["ok"] == "true"

    sessions = db_session.query(AuthSession).filter(AuthSession.user_id == user.id).all()
    assert len(sessions) == 1
    revoked_tokens = db_session.query(RevokedToken).count()
    assert revoked_tokens >= 1

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401


def test_session_listing_and_manual_revoke(client, db_session: Session) -> None:
    user = create_user(db_session, username="session_user", role=UserRole.editor)
    login_state = login(client, username=user.username, password=DEFAULT_PASSWORD)

    _, _ = create_tokens_for_user(db_session, user=user)

    list_response = client.get("/api/auth/sessions")
    assert list_response.status_code == 200
    sessions = list_response.json()
    assert len(sessions) >= 2

    target = next(item for item in sessions if not item["is_current"])
    revoke_response = client.delete(
        f"/api/auth/sessions/{target['id']}",
        headers={"x-csrf-token": login_state["csrf"]},
    )
    assert revoke_response.status_code == 200

    revoked = (
        db_session.query(AuthSession).filter(AuthSession.id == uuid.UUID(target["id"])).first()
    )
    assert revoked is not None
    assert revoked.revoked_at is not None


def test_csrf_required_for_logout_when_authenticated(client, db_session: Session) -> None:
    user = create_user(db_session, username="csrf_logout_user", role=UserRole.editor)
    login(client, username=user.username, password=DEFAULT_PASSWORD)

    response = client.post("/api/auth/logout")
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"
