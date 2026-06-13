from __future__ import annotations

from app.core.security import hash_token
from app.models.auth_session import PasswordResetToken
from app.services.auth_security import hash_password_reset_context
from tests.factories import create_user


def test_password_reset_request_stores_fingerprinted_context(
    client, db_session, monkeypatch
) -> None:
    user = create_user(db_session, username="reset_context_user", password="Password123!@#")

    monkeypatch.setattr("app.api.routers.auth.get_client_ip", lambda request: "203.0.113.42")

    response = client.post(
        "/api/auth/password-reset/request",
        json={"username": user.username},
        headers={"user-agent": "CreatorHub Test Browser/1.0"},
    )

    assert response.status_code == 200
    assert response.json()["reset_token"] is None

    token_row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    assert token_row is not None

    expected_ip_hash, expected_ua_hash = hash_password_reset_context(
        "203.0.113.42", "CreatorHub Test Browser/1.0"
    )
    assert token_row.requested_ip == expected_ip_hash
    assert token_row.requested_user_agent == expected_ua_hash


def test_password_reset_confirm_rejects_context_mismatch(client, db_session, monkeypatch) -> None:
    user = create_user(db_session, username="reset_mismatch_user", password="Password123!@#")

    monkeypatch.setattr("app.api.routers.auth.get_client_ip", lambda request: "198.51.100.10")
    request_response = client.post(
        "/api/auth/password-reset/request",
        json={"username": user.username},
        headers={"user-agent": "CreatorHub Test Browser/1.0"},
    )
    assert request_response.status_code == 200
    assert request_response.json()["reset_token"] is None

    reset_token = "test-reset-token-context-mismatch"
    token_row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    assert token_row is not None
    token_row.token_hash = hash_token(reset_token)
    db_session.commit()

    monkeypatch.setattr("app.api.routers.auth.get_client_ip", lambda request: "198.51.101.99")
    confirm_response = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "Password456!@#"},
        headers={"user-agent": "CreatorHub Test Browser/1.0"},
    )

    assert confirm_response.status_code == 400
    assert "context mismatch" in confirm_response.json()["detail"].lower()
