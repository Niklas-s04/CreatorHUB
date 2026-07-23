from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import UserRole
from tests.factories import DEFAULT_PASSWORD, create_user, login


def test_old_csrf_rejected_after_logout(client, db_session: Session) -> None:
    user = create_user(db_session, username="csrf_rotation_user", role=UserRole.editor)
    login_state = login(client, username=user.username, password=DEFAULT_PASSWORD)
    old_csrf = login_state["csrf"]
    old_access_cookie = login_state["access_cookie"]
    assert old_csrf
    assert old_access_cookie

    logout_response = client.post("/api/auth/logout", headers={"x-csrf-token": old_csrf})

    assert logout_response.status_code == 200
    new_csrf = client.cookies.get(settings.CSRF_COOKIE_NAME)
    assert new_csrf
    assert new_csrf != old_csrf

    client.cookies.set(settings.AUTH_ACCESS_COOKIE_NAME, old_access_cookie)
    response = client.delete(
        f"/api/auth/sessions/{uuid.uuid4()}",
        headers={"x-csrf-token": old_csrf},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "CSRF validation failed"
