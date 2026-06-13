from __future__ import annotations

import uuid
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_csrf_token
from app.core.web_security import CsrfProtectionMiddleware, SecurityHeadersMiddleware
from app.models.user import UserRole
from app.services.audit import redact_audit_data
from app.services.outbound_http import OutboundRequestError, _validate_url
from tests.factories import create_user, login


def _png_bytes(width: int = 2, height: int = 2) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(20, 40, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_ssrf_localhost_blocked_regression() -> None:
    with pytest.raises(OutboundRequestError, match="localhost blocked"):
        _validate_url(
            "https://localhost/internal",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_private_ip_blocked_regression() -> None:
    with pytest.raises(OutboundRequestError, match="blocked IP"):
        _validate_url(
            "https://10.0.0.5/internal",
            require_https=True,
            allow_private_ips=False,
            allowed_ports={443},
            allowed_hosts=None,
            sensitive_hosts=None,
        )


def test_ssrf_non_https_rejected_regression() -> None:
    with pytest.raises(OutboundRequestError, match="Only HTTPS"):
        _validate_url(
            "http://example.com/file",
            require_https=True,
            allow_private_ips=True,
            allowed_ports={80, 443},
            allowed_hosts={"example.com"},
            sensitive_hosts=None,
        )


def test_csrf_rotation_on_logout_regression(client, db_session: Session) -> None:
    user = create_user(db_session, username="csrf_rotation_regression", role=UserRole.editor)
    state = login(client, username=user.username)
    old_csrf = state["csrf"]

    response = client.post("/api/auth/logout", headers={"x-csrf-token": old_csrf})

    assert response.status_code == 200
    set_cookie_values = response.headers.get_list("set-cookie")
    csrf_headers = [value for value in set_cookie_values if value.startswith("creatorhub_csrf=")]
    assert csrf_headers, "Expected CSRF cookie rotation on logout"

    new_token = csrf_headers[0].split(";", 1)[0].split("=", 1)[1]
    assert new_token
    assert new_token != old_csrf


def test_csrf_blocks_account_delete_without_header_regression() -> None:
    app = FastAPI()
    app.add_middleware(
        CsrfProtectionMiddleware,
        auth_cookie_name=settings.AUTH_ACCESS_COOKIE_NAME,
        csrf_cookie_name=settings.CSRF_COOKIE_NAME,
    )

    @app.delete("/api/auth/account")
    def delete_account() -> dict[str, str]:
        return {"ok": "true"}

    client = TestClient(app)
    session_id = str(uuid.uuid4())
    access = create_access_token(
        subject="csrf-user",
        role="editor",
        session_id=session_id,
        jti="csrf-exempt-jti",
    )
    client.cookies.set(settings.AUTH_ACCESS_COOKIE_NAME, access)
    client.cookies.set(settings.CSRF_COOKIE_NAME, create_csrf_token(session_id))

    response = client.delete("/api/auth/account")
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_upload_image_bomb_rejected_regression(
    client, app, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = create_user(db_session, username="image_bomb_regression", role=UserRole.admin)

    from app.api import deps

    app.dependency_overrides[deps.get_current_user] = lambda: admin
    monkeypatch.setattr(settings, "UPLOAD_MAX_IMAGE_PIXELS", 1)

    response = client.post(
        "/api/assets/upload",
        data={
            "owner_type": "product",
            "owner_id": str(uuid.uuid4()),
            "kind": "image",
        },
        files={"file": ("tiny.png", _png_bytes(2, 2), "image/png")},
    )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "pixel" in detail or "validation" in detail or "signature" in detail


def test_cookie_secure_flag_set_regression(
    client, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = create_user(db_session, username="cookie_secure_regression", role=UserRole.editor)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SECURE", True)

    response = client.post(
        "/api/auth/token",
        data={"username": user.username, "password": "VeryStrong!Pass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    set_cookie_values = response.headers.get_list("set-cookie")
    auth_cookie_headers = [
        value
        for value in set_cookie_values
        if value.startswith("creatorhub_access=") or value.startswith("creatorhub_refresh=")
    ]
    assert auth_cookie_headers
    assert all("Secure" in header for header in auth_cookie_headers)


def test_auth_cookie_samesite_strict_regression(
    client, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = create_user(db_session, username="cookie_samesite_regression", role=UserRole.editor)
    monkeypatch.setattr(settings, "AUTH_COOKIE_SAMESITE", "strict")

    response = client.post(
        "/api/auth/token",
        data={"username": user.username, "password": "VeryStrong!Pass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    set_cookie_values = response.headers.get_list("set-cookie")
    auth_cookie_headers = [
        value
        for value in set_cookie_values
        if value.startswith("creatorhub_access=") or value.startswith("creatorhub_refresh=")
    ]
    assert auth_cookie_headers
    assert all("SameSite=strict" in header for header in auth_cookie_headers)


def test_csp_header_strict_regression(client) -> None:
    response = client.post("/api/auth/token", data={"username": "x", "password": "x"})
    csp = response.headers.get("Content-Security-Policy", "")

    assert "default-src 'none'" in csp
    assert "img-src 'self'" in csp
    assert "require-trusted-types-for 'script'" in csp
    assert "unsafe-inline" not in csp


def test_hsts_preload_header_regression() -> None:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_seconds=31536000,
        trust_proxy_headers=False,
        env="prod",
    )

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/ok")

    hsts = response.headers.get("Strict-Transport-Security", "")
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


def test_audit_log_sensitives_redacted_regression() -> None:
    payload = {
        "password": "secret",
        "nested": {"access_token": "token", "note": "safe"},
        "items": [{"mfa_secret": "value"}, {"value": 7}],
    }

    redacted = redact_audit_data(payload)

    assert redacted["password"] == "***REDACTED***"
    assert redacted["nested"]["access_token"] == "***REDACTED***"
    assert redacted["nested"]["note"] == "safe"
    assert redacted["items"][0]["mfa_secret"] == "***REDACTED***"
